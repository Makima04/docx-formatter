"""Redeem code API routes."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

from app.core import redeem
from app.config import settings

router = APIRouter(prefix="/api/redeem", tags=["redeem"])


# ── Admin auth dependency ─────────────────────────────────────────────

async def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Verify the admin API key. Required for all /admin endpoints."""
    if not settings.admin_api_key:
        raise HTTPException(503, detail="Admin API key not configured on server")
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(403, detail="Invalid admin key")


# ── Request models ────────────────────────────────────────────────────

class CheckRequest(BaseModel):
    code: str


class CreateCodeRequest(BaseModel):
    code: str
    total_quota: int
    expires_at: Optional[str] = None


class UpdateCodeRequest(BaseModel):
    total_quota: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[str] = None
    clear_expires: bool = False


# ── Public endpoints ──────────────────────────────────────────────────

@router.post("/check")
async def check_code(req: CheckRequest):
    """Validate a redeem code and return remaining quota."""
    result = redeem.validate_code(req.code)
    if not result["valid"]:
        raise HTTPException(403, detail=result["error"])
    return {"valid": True, "remaining": result["remaining"]}


# ── Admin endpoints ───────────────────────────────────────────────────

@router.get("/admin/codes")
async def list_codes(_: None = Depends(verify_admin_key)):
    """List all redeem codes."""
    return redeem.list_codes()


@router.post("/admin/codes")
async def create_code(req: CreateCodeRequest, _: None = Depends(verify_admin_key)):
    """Create a new redeem code."""
    if req.total_quota <= 0:
        raise HTTPException(400, "total_quota must be positive")
    return redeem.create_code(req.code, req.total_quota, req.expires_at)


@router.put("/admin/codes/{code_id}")
async def update_code(code_id: int, req: UpdateCodeRequest,
                      _: None = Depends(verify_admin_key)):
    """Update a redeem code's quota, active status, or expiry."""
    if not redeem.update_code(code_id, req.total_quota, req.is_active, req.expires_at, req.clear_expires):
        raise HTTPException(404, detail="Code not found or nothing to update")
    return {"ok": True}


@router.delete("/admin/codes/{code_id}")
async def delete_code(code_id: int, _: None = Depends(verify_admin_key)):
    """Delete a redeem code."""
    if not redeem.delete_code(code_id):
        raise HTTPException(404, detail="Code not found")
    return {"ok": True}
