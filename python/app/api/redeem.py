"""Redeem code API routes."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from app.core import redeem

router = APIRouter(prefix="/api/redeem", tags=["redeem"])


class CheckRequest(BaseModel):
    code: str


class CreateCodeRequest(BaseModel):
    code: str
    total_quota: int
    expires_at: Optional[str] = None


@router.post("/check")
async def check_code(req: CheckRequest):
    """Validate a redeem code and return remaining quota."""
    result = redeem.validate_code(req.code)
    if not result["valid"]:
        raise HTTPException(403, detail=result["error"])
    return {"valid": True, "remaining": result["remaining"]}


@router.get("/admin/codes")
async def list_codes():
    """List all redeem codes. In production, protect with admin auth."""
    return redeem.list_codes()


@router.post("/admin/codes")
async def create_code(req: CreateCodeRequest):
    """Create a new redeem code. In production, protect with admin auth."""
    if req.total_quota <= 0:
        raise HTTPException(400, "total_quota must be positive")
    return redeem.create_code(req.code, req.total_quota, req.expires_at)
