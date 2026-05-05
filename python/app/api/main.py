"""FastAPI application — HTTP API for document formatting."""

from __future__ import annotations
import asyncio
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import TaskInfo, TaskStatus
from app.core.pipeline import run_format_pipeline, get_task, create_task
from app.core.llm_client import LLMClient
from app.core.redeem import validate_code, consume_quota, refund_quota
from app.db import init_db

import os

logger = logging.getLogger(__name__)

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

app = FastAPI(title=settings.app_name, version="0.3.0")

# CORS
_origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_semaphore = asyncio.Semaphore(settings.max_workers)
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> Optional[LLMClient]:
    global _llm_client
    if _llm_client is None and settings.llm_api_key:
        _llm_client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    return _llm_client


async def _run_task(task_id: str, source_path: Path, code: Optional[str] = None, **kwargs):
    async with _semaphore:
        try:
            await run_format_pipeline(task_id=task_id, source_path=source_path,
                                       llm_client=get_llm_client(), **kwargs)
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            if code:
                refund_quota(code, 1)


@app.on_event("startup")
async def startup():
    init_db()
    # Share LLM client with batch module
    from app.api.batch import set_batch_llm_client
    set_batch_llm_client(get_llm_client())


# ── Register sub-routers ──────────────────────────────────────────────

from app.api.redeem import router as redeem_router
from app.api.templates import router as templates_router
from app.api.batch import router as batch_router

app.include_router(redeem_router)
app.include_router(templates_router)
app.include_router(batch_router)


# ── Core endpoints ────────────────────────────────────────────────────

@app.post("/api/format")
async def format_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Source .docx file"),
    x_redeem_code: str = Header(..., alias="X-Redeem-Code"),
    template_name: Optional[str] = Form(None),
    template_id: Optional[int] = Form(None),
    template_file: Optional[UploadFile] = File(None),
    template_description: Optional[str] = Form(None),
    page_number_format: Optional[str] = Form(None, description="Page number format: decimal, upperRoman, lowerRoman"),
    page_number_start: Optional[int] = Form(None, description="Starting page number"),
):
    # Validate redeem code
    check = validate_code(x_redeem_code)
    if not check["valid"]:
        raise HTTPException(403, detail=check["error"])

    if not file.filename or not file.filename.lower().endswith('.docx'):
        raise HTTPException(400, "Only .docx files are supported")

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(400, f"File too large (max {settings.max_upload_size_mb}MB)")

    # Consume quota
    if not consume_quota(x_redeem_code):
        raise HTTPException(403, detail="quota_exhausted")

    task_id = str(uuid.uuid4())[:8]
    source_path = Path(settings.upload_dir) / f"{task_id}_{file.filename}"
    source_path.write_bytes(content)

    template_docx_path = None
    if template_file and template_file.filename:
        tpl_content = await template_file.read()
        template_docx_path = Path(settings.upload_dir) / f"{task_id}_template.docx"
        template_docx_path.write_bytes(tpl_content)

    # Resolve template_name from template_id
    tpl_name = template_name
    if template_id and not tpl_name:
        from app.db import get_db
        with get_db() as conn:
            row = conn.execute("SELECT name FROM templates WHERE id = ?", (template_id,)).fetchone()
            if row:
                tpl_name = row["name"]

    create_task(task_id)

    background_tasks.add_task(
        _run_task, task_id=task_id, source_path=source_path, code=x_redeem_code,
        template_name=tpl_name, template_docx_path=template_docx_path,
        template_description=template_description,
    )

    return {"task_id": task_id, "status": "pending"}


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str) -> TaskInfo:
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(400, f"Task not completed (status: {task.status})")

    upload_dir = Path(settings.upload_dir)
    for f in upload_dir.glob(f"{task_id}_*.docx"):
        if not f.name.startswith(f"{task_id}_template"):
            formatted = f.parent / f"formatted_{f.name}"
            if formatted.exists():
                return FileResponse(
                    formatted,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename=f"formatted_{task_id}.docx",
                )
    raise HTTPException(404, "Output file not found")


# ── Serve frontend static files ──────────────────────────────────────

_static_dir = Path(__file__).parent.parent.parent / "static"

if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA — fall back to index.html for client-side routing."""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_static_dir / "index.html"))
