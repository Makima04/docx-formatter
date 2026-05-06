"""Redeem code API routes."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.core import redeem
from app.api.admin import verify_admin_key

router = APIRouter(prefix="/api/redeem", tags=["redeem"])


# ── Request models ────────────────────────────────────────────────────

class CheckRequest(BaseModel):
    code: str


class CreateCodeRequest(BaseModel):
    code: Optional[str] = None
    total_quota: int
    expires_at: Optional[str] = None
    prefix: Optional[str] = None
    count: int = 1


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
    """Create new redeem code(s).

    - If ``code`` is provided, creates a single code with that exact value.
    - If ``code`` is omitted, auto-generates ``count`` unique random codes
      (optionally prefixed with ``prefix``).
    """
    if req.total_quota <= 0:
        raise HTTPException(400, "total_quota must be positive")

    count = max(req.count, 1)

    if req.code:
        return redeem.create_code(req.code, req.total_quota, req.expires_at)

    created = []
    for _ in range(count):
        code = redeem.generate_unique_code(prefix=req.prefix or "")
        redeem.create_code(code, req.total_quota, req.expires_at)
        created.append(code)

    return {"codes": created}


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
