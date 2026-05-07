"""Layout validator — checks PDF rendering against expected layout rules."""

from __future__ import annotations
import logging
import re
from typing import Optional

from app.models import ValidationReport, ValidationIssue, SeverityLevel

logger = logging.getLogger(__name__)

# Page number patterns (Arabic, Roman, Chinese)
_PAGE_NUM_RE = re.compile(
    r'^\s*(\d+|[ivxlcdm]+|[IVXLCDM]+|[一二三四五六七八九十百]+)\s*$'
)


def _group_chars_into_lines(chars: list[dict], y_tolerance: float = 2.0) -> list[dict]:
    """Group character-level data into text lines for easier analysis."""
    if not chars:
        return []
    sorted_chars = sorted(chars, key=lambda c: (c["y0"], c["x0"]))
    lines: list[list[dict]] = []
    current_line: list[dict] = [sorted_chars[0]]
    for ch in sorted_chars[1:]:
        if abs(ch["y0"] - current_line[-1]["y0"]) <= y_tolerance:
            current_line.append(ch)
        else:
            lines.append(current_line)
            current_line = [ch]
    lines.append(current_line)
    result = []
    for line_chars in lines:
        text = "".join(c["text"] for c in line_chars).strip()
        if text:
            result.append({
                "x0": min(c["x0"] for c in line_chars),
                "y0": min(c["y0"] for c in line_chars),
                "x1": max(c["x1"] for c in line_chars),
                "y1": max(c["y1"] for c in line_chars),
                "text": text,
                "size": line_chars[0].get("size", 0),
                "fontname": line_chars[0].get("fontname", ""),
            })
    return result


class LayoutValidator:
    def validate(self, layout_data: dict, doc: dict, template: dict) -> ValidationReport:
        """Run all validation checks and return a ValidationReport."""
        issues: list[ValidationIssue] = []
        pages = layout_data.get("pages", [])
        paragraphs = doc.get("paragraphs", [])
        cover_end = doc.get("cover_end", -1)

        if not pages:
            return ValidationReport(passed=True, rendered_pages=0)

        for page_idx, page in enumerate(pages):
            page_num = page_idx + 1
            lines = _group_chars_into_lines(page.get("texts", []))

            # Check 1: cover page has page number
            if page_num <= (cover_end // 30 + 1) and cover_end > 0:
                for line in lines:
                    stripped = line["text"].strip()
                    if _PAGE_NUM_RE.match(stripped) and stripped:
                        page_height = page.get("height", 842)
                        if line["y0"] > page_height * 0.85:
                            issues.append(ValidationIssue(
                                issue_id="cover_page_number",
                                severity=SeverityLevel.P1_STRUCTURAL,
                                message=f"封面页面存在页码: '{stripped}'",
                                page_number=page_num,
                                auto_fixable=True,
                            ))
                            break

            # Check 2: heading orphan (heading at page bottom, last 15% of page)
            page_height = page.get("height", 842)
            for line in lines:
                if line["y0"] > page_height * 0.85:
                    if self._looks_like_heading(line):
                        issues.append(ValidationIssue(
                            issue_id="heading_orphan",
                            severity=SeverityLevel.P2_LAYOUT,
                            message=f"标题出现在页面底部: '{line['text'][:40]}'",
                            page_number=page_num,
                            auto_fixable=True,
                        ))

            # Check 3: large blank gap (>40% of page height with no text)
            if lines:
                max_gap = 0
                for i in range(1, len(lines)):
                    gap = lines[i]["y0"] - lines[i-1]["y1"]
                    if gap > max_gap:
                        max_gap = gap
                if max_gap > page_height * 0.4:
                    issues.append(ValidationIssue(
                        issue_id="large_blank_gap",
                        severity=SeverityLevel.P2_LAYOUT,
                        message=f"页面存在大面积空白 ({max_gap:.0f}pt, {max_gap/page_height*100:.0f}%)",
                        page_number=page_num,
                        auto_fixable=True,
                    ))

            # Check 4: table overflow
            page_width = page.get("width", 595)
            margin_right_cm = template.get("page", {}).get("margin_right_cm", 3.17)
            margin_left_cm = template.get("page", {}).get("margin_left_cm", 3.17)
            content_right = page_width - margin_right_cm * 28.35
            content_left = margin_left_cm * 28.35
            for table in page.get("tables", []):
                bbox = table.get("bbox", [0, 0, 0, 0])
                if bbox[0] < content_left - 5 or bbox[2] > content_right + 5:
                    issues.append(ValidationIssue(
                        issue_id="table_overflow",
                        severity=SeverityLevel.P2_LAYOUT,
                        message="表格超出页面内容区域",
                        page_number=page_num,
                        target_type="table",
                        auto_fixable=True,
                    ))

        # Check 5: figure-caption split (image and next text on different pages)
        self._check_figure_caption_split(pages, paragraphs, issues)

        # Check 6: chapter 1 on odd page
        self._check_chapter1_odd_page(paragraphs, pages, issues)

        passed = not any(i.severity in (SeverityLevel.P0_CORRUPT, SeverityLevel.P1_STRUCTURAL)
                         for i in issues)
        return ValidationReport(
            passed=passed,
            issues=issues,
            metrics={"pages_checked": len(pages), "issues_found": len(issues)},
            rendered_pages=len(pages),
        )

    def _looks_like_heading(self, line: dict) -> bool:
        """Heuristic: larger font, bold, or short centered text."""
        if line.get("size", 0) >= 14:
            return True
        if "Bold" in line.get("fontname", ""):
            return True
        return False

    def _check_figure_caption_split(self, pages: list, paragraphs: list, issues: list):
        """Check that images and their captions are on the same page."""
        # Group image indices with their caption paragraph indices
        figure_captions = []
        for i, p in enumerate(paragraphs):
            if p.get("paragraph_type") == "caption_figure":
                figure_captions.append((i, p.get("text", "")[:50]))

        if not figure_captions or not pages:
            return

        # Approximate: each page holds ~30 paragraphs
        para_per_page = max(1, len(paragraphs) // len(pages))
        for para_idx, caption_text in figure_captions:
            # The image is typically the paragraph before the caption
            img_para_idx = para_idx - 1
            img_page = img_para_idx // para_per_page + 1
            cap_page = para_idx // para_per_page + 1
            if img_page != cap_page and abs(img_page - cap_page) == 1:
                issues.append(ValidationIssue(
                    issue_id="figure_caption_split",
                    severity=SeverityLevel.P2_LAYOUT,
                    message=f"图片与图题可能分页: '{caption_text}'",
                    page_number=cap_page,
                    para_index=para_idx,
                    target_type="figure",
                    auto_fixable=True,
                ))

    def _check_chapter1_odd_page(self, paragraphs: list, pages: list, issues: list):
        """Check that the first Heading1 starts on an odd page."""
        for i, p in enumerate(paragraphs):
            if p.get("paragraph_type") == "heading1":
                para_per_page = max(1, len(paragraphs) // max(len(pages), 1))
                page_num = i // para_per_page + 1
                if page_num > 1 and page_num % 2 == 0:
                    issues.append(ValidationIssue(
                        issue_id="chapter1_odd_page",
                        severity=SeverityLevel.P1_STRUCTURAL,
                        message=f"第一章起始页为偶数页 (第{page_num}页)",
                        page_number=page_num,
                        para_index=i,
                        auto_fixable=True,
                    ))
                break
