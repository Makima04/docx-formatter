"""Confirmation manager — generates user-facing confirmation items for low-confidence decisions."""

from __future__ import annotations
import logging
from typing import Optional

from app.models import (
    ConfirmationItem, ValidationReport, FormatRule,
    RepairAction, SeverityLevel,
)

logger = logging.getLogger(__name__)

# High-risk operations that always require confirmation regardless of confidence
HIGH_RISK_OPS = {
    "replace_cover",
    "split_large_table",
    "insert_blank_page",
    "modify_formula_content",
    "modify_keyword_order",
}


class ConfirmationManager:
    """Generates and manages user confirmation items."""

    def generate_confirmations(
        self,
        doc: dict,
        report: Optional[ValidationReport] = None,
        rules: Optional[list[FormatRule]] = None,
        actions: Optional[list[RepairAction]] = None,
    ) -> list[ConfirmationItem]:
        """Generate confirmation items from various pipeline outputs."""
        items: list[ConfirmationItem] = []
        counter = 0

        # 1. Low-confidence classifications
        for p in doc.get("paragraphs", []):
            conf = p.get("confidence", 0)
            if 0.65 <= conf < 0.85:
                counter += 1
                items.append(ConfirmationItem(
                    id=f"cls_{counter}",
                    category="classification",
                    description=f"段落分类置信度较低 ({conf:.0%}): \"{p.get('text', '')[:60]}\" "
                                f"→ {p.get('paragraph_type', 'unknown')}",
                    options=[
                        {"label": "接受当前分类", "value": p.get("paragraph_type"), "recommended": True},
                        {"label": "标记为正文", "value": "body", "recommended": False},
                    ],
                    risk_level="low",
                ))
            elif conf < 0.65:
                counter += 1
                items.append(ConfirmationItem(
                    id=f"cls_{counter}",
                    category="classification",
                    description=f"段落分类置信度极低 ({conf:.0%}): \"{p.get('text', '')[:60]}\"",
                    options=[
                        {"label": "标记为正文", "value": "body", "recommended": True},
                        {"label": "标记为标题1", "value": "heading1", "recommended": False},
                        {"label": "标记为标题2", "value": "heading2", "recommended": False},
                    ],
                    risk_level="medium",
                ))

        # 2. Unresolved validation issues
        if report:
            for issue in report.issues:
                if issue.severity in (SeverityLevel.P0_CORRUPT, SeverityLevel.P1_STRUCTURAL):
                    counter += 1
                    items.append(ConfirmationItem(
                        id=f"val_{counter}",
                        category="validation",
                        description=issue.message,
                        options=[
                            {"label": "尝试自动修复", "value": "auto_fix", "recommended": True},
                            {"label": "忽略此问题", "value": "ignore", "recommended": False},
                        ],
                        risk_level="high" if issue.severity == SeverityLevel.P0_CORRUPT else "medium",
                    ))

        # 3. Pending rules (unknown targets)
        if rules:
            for rule in rules:
                if rule.status == "pending" or rule.requires_user_confirmation:
                    counter += 1
                    items.append(ConfirmationItem(
                        id=f"rule_{counter}",
                        category="rule_conflict",
                        description=f"格式规则需要确认: [{rule.target}] {rule.constraint}",
                        options=[
                            {"label": "应用此规则", "value": "apply", "recommended": True},
                            {"label": "跳过此规则", "value": "skip", "recommended": False},
                        ],
                        risk_level="medium",
                    ))

        # 4. High-risk repair actions
        if actions:
            for action in actions:
                if action.risk_level == "high" or action.action_type in HIGH_RISK_OPS:
                    counter += 1
                    items.append(ConfirmationItem(
                        id=f"repair_{counter}",
                        category="repair",
                        description=f"高风险修复操作: {action.action_type} (目标: {action.target_index})",
                        options=[
                            {"label": "执行修复", "value": "execute", "recommended": True},
                            {"label": "跳过修复", "value": "skip", "recommended": False},
                        ],
                        risk_level="high",
                    ))

        return items

    def apply_confirmation(
        self,
        items: list[ConfirmationItem],
        item_id: str,
        choice: str,
    ) -> list[ConfirmationItem]:
        """Apply a user's choice to a confirmation item. Returns updated items."""
        for item in items:
            if item.id == item_id:
                item.user_choice = choice
                item.auto_resolved = True
                logger.info(f"Confirmation {item_id}: user chose '{choice}'")
                break
        return items

    def pending_items(self, items: list[ConfirmationItem]) -> list[ConfirmationItem]:
        """Return items that haven't been resolved yet."""
        return [i for i in items if not i.auto_resolved]
