"""Template CRUD API routes."""

from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db import get_db

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    config_json: str  # TemplateConfig JSON string


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[str] = None


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
    }


@router.get("")
async def list_templates():
    """List all templates (builtin + custom)."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY is_builtin DESC, id ASC").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{template_id}")
async def get_template(template_id: int):
    """Get a single template with full config."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Template not found")
    result = _row_to_dict(row)
    result["config_json"] = row["config_json"]
    return result


@router.post("")
async def create_template(req: TemplateCreate):
    """Create a custom template."""
    # Validate JSON
    try:
        json.loads(req.config_json)
    except json.JSONDecodeError:
        raise HTTPException(400, "config_json is not valid JSON")

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO templates (name, description, config_json, is_builtin) VALUES (?, ?, ?, 0)",
            (req.name, req.description, req.config_json),
        )
        template_id = cursor.lastrowid

    return {"id": template_id, "name": req.name, "description": req.description}


@router.put("/{template_id}")
async def update_template(template_id: int, req: TemplateUpdate):
    """Update a template (only custom templates)."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Template not found")
        if row["is_builtin"]:
            raise HTTPException(403, "Cannot modify builtin templates")

        updates = {}
        if req.name is not None:
            updates["name"] = req.name
        if req.description is not None:
            updates["description"] = req.description
        if req.config_json is not None:
            try:
                json.loads(req.config_json)
            except json.JSONDecodeError:
                raise HTTPException(400, "config_json is not valid JSON")
            updates["config_json"] = req.config_json

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [template_id]
            conn.execute(f"UPDATE templates SET {set_clause} WHERE id = ?", values)

    return {"id": template_id, "updated": list(updates.keys())}


@router.delete("/{template_id}")
async def delete_template(template_id: int):
    """Delete a custom template."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Template not found")
        if row["is_builtin"]:
            raise HTTPException(403, "Cannot delete builtin templates")
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))

    return {"deleted": template_id}
