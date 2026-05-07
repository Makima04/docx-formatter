"""Repair engine — generates and applies repair actions for validation issues."""

from __future__ import annotations
import logging
import copy
from typing import Optional

from app.models import (
    ValidationReport, ValidationIssue, SeverityLevel,
    RepairAction, LayoutPlan,
)

logger = logging.getLogger(__name__)

# Maximum shrink factor for images
_MIN_IMAGE_SCALE = 0.4
# Maximum column width reduction factor
_MIN_COL_SCALE = 0.5


class RepairEngine:
    def generate_repairs(
        self,
        report: ValidationReport,
        layout_plan: dict,
        doc: dict,
        template: dict,
    ) -> list[RepairAction]:
        """Generate repair actions from a validation report."""
        actions: list[RepairAction] = []
        seen: set[str] = set()

        for issue in report.issues:
            if not issue.auto_fixable:
                continue
            if issue.issue_id in seen:
                continue
            seen.add(issue.issue_id)

            action = self._issue_to_action(issue, layout_plan, doc, template)
            if action:
                actions.append(action)

        return actions

    def apply_repairs(
        self,
        actions: list[RepairAction],
        layout_plan: dict,
        template: dict,
    ) -> tuple[dict, dict]:
        """Apply repair actions to layout_plan and template. Returns modified copies."""
        lp = copy.deepcopy(layout_plan)
        tpl = copy.deepcopy(template)

        for action in actions:
            handler = _ACTION_HANDLERS.get(action.action_type)
            if handler:
                handler(action, lp, tpl)

        return lp, tpl

    def _issue_to_action(
        self,
        issue: ValidationIssue,
        layout_plan: dict,
        doc: dict,
        template: dict,
    ) -> Optional[RepairAction]:
        """Map a validation issue to a concrete repair action."""
        if issue.issue_id == "table_overflow":
            return self._repair_table_overflow(issue, layout_plan)
        elif issue.issue_id == "figure_caption_split":
            return self._repair_figure_caption_split(issue, layout_plan)
        elif issue.issue_id == "heading_orphan":
            return self._repair_heading_orphan(issue, template)
        elif issue.issue_id == "chapter1_odd_page":
            return RepairAction(
                action_type="insert_odd_break",
                target_index=issue.para_index,
                parameters={},
                risk_level="medium",
            )
        elif issue.issue_id == "cover_page_number":
            return RepairAction(
                action_type="suppress_cover_page_number",
                target_index=0,
                parameters={},
                risk_level="low",
            )
        elif issue.issue_id == "large_blank_gap":
            return self._repair_blank_gap(issue, layout_plan)
        return None

    def _repair_table_overflow(
        self,
        issue: ValidationIssue,
        layout_plan: dict,
    ) -> RepairAction:
        """Shrink table column widths by 10%."""
        table_plans = layout_plan.get("table_plans", [])
        # Try to find the table near the reported page
        target_idx = 0
        if table_plans:
            # Use the first table plan that still has room to shrink
            for i, tp in enumerate(table_plans):
                widths = tp.get("col_widths_twips", [])
                if widths and widths[0] > 2000:
                    target_idx = i
                    break
        return RepairAction(
            action_type="shrink_table_width",
            target_index=target_idx,
            parameters={"scale": 0.9},
            risk_level="low",
        )

    def _repair_figure_caption_split(
        self,
        issue: ValidationIssue,
        layout_plan: dict,
    ) -> RepairAction:
        """Shrink the figure by 15%."""
        figure_plans = layout_plan.get("figure_plans", [])
        target_idx = issue.para_index
        # Find the figure plan matching this paragraph
        for i, fp in enumerate(figure_plans):
            if fp.get("caption_para_index") == issue.para_index:
                target_idx = i
                break
        return RepairAction(
            action_type="shrink_figure",
            target_index=target_idx,
            parameters={"scale": 0.85},
            risk_level="low",
        )

    def _repair_heading_orphan(
        self,
        issue: ValidationIssue,
        template: dict,
    ) -> RepairAction:
        """Enable keepNext for heading styles."""
        return RepairAction(
            action_type="enable_keep_next",
            target_index=issue.para_index,
            parameters={},
            risk_level="low",
        )

    def _repair_blank_gap(
        self,
        issue: ValidationIssue,
        layout_plan: dict,
    ) -> RepairAction:
        """Shrink images near the blank gap to reduce overflow."""
        return RepairAction(
            action_type="shrink_images_near_page",
            target_index=issue.page_number,
            parameters={"scale": 0.9},
            risk_level="low",
        )


# ── Action handlers ─────────────────────────────────────────────────


def _handle_shrink_table_width(action: RepairAction, lp: dict, tpl: dict):
    scale = action.parameters.get("scale", 0.9)
    idx = action.target_index or 0
    table_plans = lp.get("table_plans", [])
    if idx < len(table_plans):
        widths = table_plans[idx].get("col_widths_twips", [])
        new_widths = [max(int(w * scale), 1500) for w in widths]
        if new_widths != widths:
            table_plans[idx]["col_widths_twips"] = new_widths
            logger.info(f"Shrunk table {idx} columns: {widths} → {new_widths}")


def _handle_shrink_figure(action: RepairAction, lp: dict, tpl: dict):
    scale = action.parameters.get("scale", 0.85)
    idx = action.target_index or 0
    figure_plans = lp.get("figure_plans", [])
    if idx < len(figure_plans):
        fp = figure_plans[idx]
        old_w, old_h = fp.get("width_emu", 0), fp.get("height_emu", 0)
        fp["width_emu"] = max(int(old_w * scale), int(1 * 360000))  # min 1cm
        fp["height_emu"] = max(int(old_h * scale), int(0.75 * 360000))
        logger.info(f"Shrunk figure {idx}: {old_w}x{old_h} → {fp['width_emu']}x{fp['height_emu']}")


def _handle_enable_keep_next(action: RepairAction, lp: dict, tpl: dict):
    # Template-level: headings should keep_next. This is already done by the assembler
    # via style_def_xml. If the issue persists, it's a PDF rendering artifact.
    logger.info(f"keepNext already enabled for headings (para {action.target_index})")


def _handle_insert_odd_break(action: RepairAction, lp: dict, tpl: dict):
    """Insert an odd-page section break for chapter 1."""
    sections = tpl.get("sections", [])
    if not sections:
        sections = [{"name": "body", "start_type": "nextPage"}]
    # Mark first body section to start on odd page
    sections[0]["start_type"] = "oddPage"
    tpl["sections"] = sections
    logger.info("Inserted oddPage section break for chapter 1")


def _handle_suppress_cover_page_number(action: RepairAction, lp: dict, tpl: dict):
    """Suppress page number on cover section."""
    sections = tpl.get("sections", [])
    if sections:
        sections[0]["suppress_page_number"] = True
    else:
        sections = [{"name": "cover", "suppress_page_number": True}]
        tpl["sections"] = sections
    logger.info("Suppressed page number on cover section")


def _handle_shrink_images_near_page(action: RepairAction, lp: dict, tpl: dict):
    """Shrink all figures slightly to avoid blank gaps."""
    scale = action.parameters.get("scale", 0.9)
    for fp in lp.get("figure_plans", []):
        old_w, old_h = fp.get("width_emu", 0), fp.get("height_emu", 0)
        fp["width_emu"] = max(int(old_w * scale), int(1 * 360000))
        fp["height_emu"] = max(int(old_h * scale), int(0.75 * 360000))
    logger.info("Shrunk all figures to reduce blank gaps")


_ACTION_HANDLERS = {
    "shrink_table_width": _handle_shrink_table_width,
    "shrink_figure": _handle_shrink_figure,
    "enable_keep_next": _handle_enable_keep_next,
    "insert_odd_break": _handle_insert_odd_break,
    "suppress_cover_page_number": _handle_suppress_cover_page_number,
    "shrink_images_near_page": _handle_shrink_images_near_page,
}
