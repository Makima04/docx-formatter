"""Batch processing API routes."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import FileResponse

from app.config import settings
from app.core.redeem import validate_code
from app.core.batch import create_batch, get_batch_status
from app.core.llm_client import LLMClient
from app.db import get_db

router = APIRouter(prefix="/api/batch", tags=["batch"])

_llm_client = None


def set_batch_llm_client(client):
    global _llm_client
    _llm_client = client


@router.post("")
async def create_batch_task(
    files: list[UploadFile] = File(..., description="Multiple .docx files"),
    x_redeem_code: str = Header(..., alias="X-Redeem-Code"),
    template_id: Optional[int] = Form(None),
    template_name: Optional[str] = Form(None),
    template_description: Optional[str] = Form(None),
):
    """Submit a batch of files for formatting."""
    # Validate code
    check = validate_code(x_redeem_code)
    if not check["valid"]:
        raise HTTPException(403, detail=check["error"])

    if not files:
        raise HTTPException(400, "No files provided")

    if len(files) > check["remaining"]:
        raise HTTPException(400, f"Not enough quota. Remaining: {check['remaining']}, requested: {len(files)}")

    # Validate all files are .docx
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".docx"):
            raise HTTPException(400, f"Only .docx files supported: {f.filename}")

    # Save files to upload dir
    file_paths: list[tuple[str, Path]] = []
    upload_dir = Path(settings.upload_dir)
    for f in files:
        content = await f.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(400, f"File too large: {f.filename}")
        save_path = upload_dir / f"batch_{f.filename}"
        save_path.write_bytes(content)
        file_paths.append((f.filename, save_path))

    # Resolve template name from ID if needed
    tpl_name = template_name
    if template_id and not template_name:
        with get_db() as conn:
            row = conn.execute("SELECT name FROM templates WHERE id = ?", (template_id,)).fetchone()
            if row:
                tpl_name = row["name"]

    try:
        batch_id = await create_batch(
            code=x_redeem_code,
            file_paths=file_paths,
            template_id=template_id,
            template_name=tpl_name,
            template_description=template_description,
            llm_client=_llm_client,
        )
    except ValueError as e:
        raise HTTPException(403, detail=str(e))

    return {"batch_id": batch_id, "total_files": len(file_paths)}


@router.get("/{batch_id}")
async def get_batch(batch_id: str):
    """Get batch processing status."""
    result = get_batch_status(batch_id)
    if not result:
        raise HTTPException(404, "Batch not found")
    return result


@router.get("/{batch_id}/download")
async def download_batch(batch_id: str):
    """Download all formatted files as a zip."""
    result = get_batch_status(batch_id)
    if not result:
        raise HTTPException(404, "Batch not found")
    if result["status"] not in ("completed", "partial"):
        raise HTTPException(400, f"Batch not ready (status: {result['status']})")

    # Collect output files
    import zipfile
    import tempfile

    upload_dir = Path(settings.upload_dir)
    zip_path = Path(tempfile.gettempdir()) / f"batch_{batch_id}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in result["items"]:
            if item["status"] == "completed":
                task_id = item["task_id"]
                for f in upload_dir.glob(f"*{task_id}*"):
                    if f.name.startswith("formatted_"):
                        zf.write(f, f.name.replace("formatted_", ""))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"batch_{batch_id}.zip",
    )
