"""Layout planner — generates a structured LayoutPlan from parsed document + template.

The plan tells the Rust assembler WHERE to place tables, WHAT column widths to use,
HOW to size figures, and WHAT formula numbers to assign. The assembler executes the
plan deterministically — no LLM involved in OpenXML generation.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models import (
    LayoutPlan, TablePlacement, TablePlan, FigurePlan, FormulaPlan,
)

logger = logging.getLogger(__name__)

# 1cm ≈ 567 twips (twentieths of a point; 1 inch = 1440 twips, 1 inch = 2.54cm)
CM_TO_TWIPS = 1440.0 / 2.54


class LayoutPlanner:
    """Generates a LayoutPlan from document data, template config, and style registry."""

    def __init__(self, doc: dict, template: dict, registry=None):
        self._doc = doc
        self._template = template
        self._registry = registry
        self._paragraphs = doc.get("paragraphs", [])
        self._tables = doc.get("tables", [])
        self._images = doc.get("images", [])

    def plan(self) -> LayoutPlan:
        """Generate the full layout plan."""
        table_placements = self._plan_table_placements()
        table_plans = self._plan_table_widths()
        figure_plans = self._plan_figures()
        formula_plans = self._plan_formulas()

        logger.info(
            f"Layout plan: {len(table_placements)} table placements, "
            f"{len(table_plans)} table plans, "
            f"{len(figure_plans)} figure plans, "
            f"{len(formula_plans)} formula plans"
        )
        return LayoutPlan(
            table_placements=table_placements,
            table_plans=table_plans,
            figure_plans=figure_plans,
            formula_plans=formula_plans,
        )

    # ── Table placement ──────────────────────────────────────────

    def _plan_table_placements(self) -> list[TablePlacement]:
        """Match CaptionTable paragraphs to tables by sequential order."""
        placements = []
        caption_indices = [
            i for i, p in enumerate(self._paragraphs)
            if p.get("paragraph_type") == "caption_table"
        ]

        matched_table_indices = set()
        for cap_i, table_i in enumerate(caption_indices):
            if cap_i < len(self._tables):
                placements.append(TablePlacement(
                    table_index=cap_i,
                    after_para_index=table_i,
                    include_caption=False,  # caption already in paragraph stream
                ))
                matched_table_indices.add(cap_i)

        # Tables without captions → append at document end
        for t_idx in range(len(self._tables)):
            if t_idx not in matched_table_indices:
                placements.append(TablePlacement(
                    table_index=t_idx,
                    after_para_index=len(self._paragraphs) - 1,
                    include_caption=True,  # need to include caption in table XML
                ))

        return placements

    # ── Table column widths ──────────────────────────────────────

    def _plan_table_widths(self) -> list[TablePlan]:
        """Calculate page-width-aware column widths for each table."""
        page = self._template.get("page", {})
        page_w = page.get("page_width_cm", 21.0)
        margin_l = page.get("margin_left_cm", 3.17)
        margin_r = page.get("margin_right_cm", 3.17)
        content_width_twips = round((page_w - margin_l - margin_r) * CM_TO_TWIPS)

        plans = []
        for t_idx, table in enumerate(self._tables):
            col_count = max(table.get("col_count", 1), 1)
            base_width = content_width_twips // col_count
            remainder = content_width_twips - base_width * col_count
            col_widths = [base_width] * col_count
            for i in range(remainder):
                col_widths[i] += 1

            plans.append(TablePlan(
                table_index=t_idx,
                col_widths_twips=col_widths,
                three_line=True,
            ))
        return plans

    # ── Figure sizing ────────────────────────────────────────────

    def _plan_figures(self) -> list[FigurePlan]:
        """Calculate figure dimensions based on page width and image aspect ratio."""
        page = self._template.get("page", {})
        figure = self._template.get("figure", {})
        page_w = page.get("page_width_cm", 21.0)
        margin_l = page.get("margin_left_cm", 3.17)
        margin_r = page.get("margin_right_cm", 3.17)
        content_width_cm = page_w - margin_l - margin_r
        max_width_cm = min(figure.get("max_width_cm", 15.0), content_width_cm)
        max_width_emu = round(max_width_cm * 360000)

        plans = []
        image_idx = 0
        for p_idx, para in enumerate(self._paragraphs):
            if para.get("paragraph_type") != "caption_figure":
                continue
            if image_idx >= len(self._images):
                break

            img = self._images[image_idx]
            w_px = img.get("width_px")
            h_px = img.get("height_px")

            if w_px and h_px and w_px > 0 and h_px > 0:
                aspect = h_px / w_px
                disp_w = max_width_emu
                disp_h = round(disp_w * aspect)
            else:
                disp_w = max_width_emu
                disp_h = round(disp_w * 0.75)

            plans.append(FigurePlan(
                image_index=image_idx,
                caption_para_index=p_idx,
                width_emu=disp_w,
                height_emu=disp_h,
            ))
            image_idx += 1

        return plans

    # ── Formula numbering ────────────────────────────────────────

    def _plan_formulas(self) -> list[FormulaPlan]:
        """Assign chapter-based numbering to formula paragraphs."""
        plans = []
        chapter = 0
        formula_counter = 0

        for p_idx, para in enumerate(self._paragraphs):
            ptype = para.get("paragraph_type", "unknown")
            if ptype == "heading1":
                chapter += 1
                formula_counter = 0
            elif ptype == "formula":
                formula_counter += 1
                plans.append(FormulaPlan(
                    para_index=p_idx,
                    chapter=chapter,
                    number=formula_counter,
                ))

        return plans
