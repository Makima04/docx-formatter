"""Formatting trace — records every decision for debugging and user reporting."""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class FormattingTrace:
    """Records formatting decisions across pipeline stages."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.entries: list[dict] = []

    def record(self, stage: str, data: dict):
        """Record a trace entry for a pipeline stage."""
        entry = {
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self.entries.append(entry)

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "entries": self.entries}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def to_user_report(self) -> str:
        """Generate a concise user-facing report."""
        auto_fixed = []
        needs_confirm = []
        cannot_fix = []

        for entry in self.entries:
            stage = entry["stage"]
            data = entry["data"]

            if stage == "repair":
                actions = data.get("actions", [])
                for a in actions:
                    auto_fixed.append(a.get("description", a.get("action_type", "")))

            if stage == "validation":
                issues = data.get("issues", [])
                for issue in issues:
                    sev = issue.get("severity", "")
                    msg = issue.get("message", "")
                    if sev in ("p0_corrupt", "p1_structural"):
                        cannot_fix.append(msg)
                    elif sev == "p2_layout":
                        if issue.get("auto_fixable"):
                            auto_fixed.append(msg)
                        else:
                            needs_confirm.append(msg)

            if stage == "confirmations":
                items = data.get("items", [])
                for item in items:
                    if not item.get("auto_resolved"):
                        needs_confirm.append(item.get("description", ""))

        parts = []
        if auto_fixed:
            parts.append(f"已自动修复：{'、'.join(auto_fixed[:5])}")
        if needs_confirm:
            parts.append(f"需要用户确认：{'、'.join(needs_confirm[:5])}")
        if cannot_fix:
            parts.append(f"无法自动处理：{'、'.join(cannot_fix[:5])}")
        if not parts:
            parts.append("排版完成，无需修复。")
        return "\n".join(parts)

    def to_developer_report(self) -> str:
        """Generate a detailed developer-facing report."""
        lines = [f"=== Formatting Trace: {self.task_id} ==="]
        for entry in self.entries:
            stage = entry["stage"]
            ts = entry["timestamp"]
            data = entry["data"]
            lines.append(f"\n[{ts}] {stage}:")
            for k, v in data.items():
                if isinstance(v, (list, dict)):
                    lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False, default=str)[:200]}")
                else:
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines)
