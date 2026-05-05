"""Redeem code — validation and quota management."""

from __future__ import annotations
import logging
from typing import Optional
from datetime import datetime

from app.db import get_db

logger = logging.getLogger(__name__)


def validate_code(code: str) -> dict:
    """Validate a redeem code and return status info.

    Returns:
        {"valid": bool, "remaining": int, "error": str | None}
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM redeem_codes WHERE code = ?", (code,)
        ).fetchone()

    if not row:
        return {"valid": False, "remaining": 0, "error": "invalid_code"}

    if not row["is_active"]:
        return {"valid": False, "remaining": 0, "error": "code_deactivated"}

    if row["expires_at"]:
        exp = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > exp:
            return {"valid": False, "remaining": 0, "error": "expired"}

    remaining = row["total_quota"] - row["used_quota"]
    if remaining <= 0:
        return {"valid": False, "remaining": 0, "error": "quota_exhausted"}

    return {"valid": True, "remaining": remaining, "error": None}


def consume_quota(code: str, amount: int = 1) -> bool:
    """Atomically consume quota. Returns True if successful."""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE redeem_codes SET used_quota = used_quota + ? "
            "WHERE code = ? AND is_active = 1 AND (used_quota + ?) <= total_quota",
            (amount, code, amount),
        )
        return result.rowcount > 0


def refund_quota(code: str, amount: int = 1):
    """Refund quota (e.g., on task failure)."""
    with get_db() as conn:
        conn.execute(
            "UPDATE redeem_codes SET used_quota = MAX(0, used_quota - ?) WHERE code = ?",
            (amount, code),
        )


def create_code(code: str, total_quota: int, expires_at: Optional[str] = None) -> dict:
    """Create a new redeem code (admin operation)."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO redeem_codes (code, total_quota, expires_at) VALUES (?, ?, ?)",
            (code, total_quota, expires_at),
        )
    return {"code": code, "total_quota": total_quota, "expires_at": expires_at}


def list_codes() -> list[dict]:
    """List all redeem codes (admin operation)."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
