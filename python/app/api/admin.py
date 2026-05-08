"""Admin settings API routes — LLM configuration and other server settings."""

from __future__ import annotations
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from app.config import settings
from app.db import get_setting, set_setting, list_llm_logs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Admin auth dependency (same as redeem) ─────────────────────────

async def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    if not settings.admin_api_key:
        raise HTTPException(503, detail="Admin API key not configured on server")
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(403, detail="Invalid admin key")


# ── LLM config endpoints ──────────────────────────────────────────

class LLMConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    concurrent_requests: Optional[int] = None


@router.get("/settings/llm")
async def get_llm_config(_: None = Depends(verify_admin_key)):
    """Get current LLM configuration (api_key is masked)."""
    api_key = get_setting("llm_api_key", "")
    base_url = get_setting("llm_base_url", settings.llm_base_url)
    model = get_setting("llm_model", settings.llm_model)
    concurrent = get_setting("llm_concurrent_requests", str(settings.llm_concurrent_requests))
    return {
        "api_key": api_key[:8] + "..." if len(api_key) > 8 else api_key,
        "base_url": base_url,
        "model": model,
        "concurrent_requests": int(concurrent) if concurrent.isdigit() else settings.llm_concurrent_requests,
    }


@router.put("/settings/llm")
async def update_llm_config(req: LLMConfigUpdate, _: None = Depends(verify_admin_key)):
    """Update LLM configuration. Persists to DB and takes effect immediately."""
    from app.core import llm_client as llm_mod
    import app.api.main as main_mod

    if req.api_key is not None:
        set_setting("llm_api_key", req.api_key)
    if req.base_url is not None:
        set_setting("llm_base_url", req.base_url)
    if req.model is not None:
        set_setting("llm_model", req.model)
    if req.concurrent_requests is not None:
        val = max(1, min(10, req.concurrent_requests))
        set_setting("llm_concurrent_requests", str(val))

    # Reset the cached LLM client so next request picks up new config
    main_mod._llm_client = None
    from app.api.batch import set_batch_llm_client
    set_batch_llm_client(None)

    return {"ok": True}


@router.get("/settings/llm/models")
async def list_llm_models(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    _: None = Depends(verify_admin_key),
):
    """Fetch available models from the LLM provider.
    Accepts optional query params so the frontend can test before saving."""
    key = api_key or get_setting("llm_api_key", "")
    url = (base_url or get_setting("llm_base_url", settings.llm_base_url)).rstrip("/")
    if not key:
        raise HTTPException(400, "API key not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{url}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            return {"models": sorted(models)}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, detail=f"Provider returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(502, detail=f"Failed to fetch models: {e}")


@router.post("/settings/llm/test")
async def test_llm_connection(req: LLMConfigUpdate, _: None = Depends(verify_admin_key)):
    """Test LLM connectivity by hitting the /models endpoint with provided or stored config."""
    key = req.api_key or get_setting("llm_api_key", "")
    url = (req.base_url or get_setting("llm_base_url", settings.llm_base_url)).rstrip("/")
    model = req.model or get_setting("llm_model", settings.llm_model)

    if not key:
        return {"ok": False, "message": "未配置 API Key"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{url}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            model_found = model in models if models else None
            return {
                "ok": True,
                "message": "连接成功",
                "model_count": len(models),
                "model_found": model_found,
            }
    except httpx.HTTPStatusError as e:
        return {"ok": False, "message": f"API 返回错误: {e.response.status_code}"}
    except httpx.ConnectError:
        return {"ok": False, "message": f"无法连接到 {url}"}
    except httpx.TimeoutException:
        return {"ok": False, "message": "连接超时"}
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {str(e)}"}


@router.get("/settings/llm/logs")
async def get_llm_logs(
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(verify_admin_key),
):
    """Get recent LLM call logs with full prompt/response content."""
    logs = list_llm_logs(limit=limit, offset=offset)
    return {"logs": logs, "total": len(logs)}
