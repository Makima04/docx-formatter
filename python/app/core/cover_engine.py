"""Cover engine — detects and extracts fields from cover pages in parsed documents.

Phase 3d: passive detection + field extraction. Does NOT inject or rebuild covers.
Extracted fields are stored for later use by the layout planner (Phase 4) and
user confirmation flow (Phase 6).
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns for extracting structured fields from cover paragraphs
_FIELD_PATTERNS = {
    'author': [
        re.compile(r'(?:姓\s*名|作\s*者)[：:\s]*(.+)'),
    ],
    'student_id': [
        re.compile(r'学\s*号[：:\s]*(\S+)'),
    ],
    'college': [
        re.compile(r'(?:学\s*院|院\s*系)[：:\s]*(.+)'),
    ],
    'major': [
        re.compile(r'专\s*业[：:\s]*(.+)'),
    ],
    'advisor': [
        re.compile(r'(?:指导|辅导)教师[：:\s]*(.+)'),
    ],
    'school': [
        re.compile(r'^(\S{2,}(?:大学|学院|研究院))'),
    ],
    'date': [
        re.compile(r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)'),
        re.compile(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'),
    ],
}


@dataclass
class CoverResult:
    """Result of cover page analysis."""
    has_cover: bool
    cover_start: Optional[int] = None
    cover_end: Optional[int] = None
    fields: dict[str, str] = field(default_factory=dict)


def _detect_cover_block(paragraphs: list[dict]) -> Optional[tuple[int, int]]:
    """Detect the cover page range in a parsed document.

    Strategy:
    1. Collect consecutive paragraphs tagged as 'cover' type
    2. Or: find all paragraphs before the first non-cover Heading1

    Returns (start_idx, end_idx) inclusive, or None if no cover detected.
    """
    if not paragraphs:
        return None

    # Strategy 1: consecutive cover-tagged paragraphs
    cover_indices = [i for i, p in enumerate(paragraphs) if p.get('paragraph_type') == 'cover']
    if len(cover_indices) >= 2:
        # Check they are consecutive (allow gaps of at most 1 empty paragraph)
        start = cover_indices[0]
        end = cover_indices[0]
        for idx in cover_indices[1:]:
            # Allow empty paragraphs between cover paragraphs
            gap_ok = all(
                not paragraphs[j].get('text', '').strip()
                for j in range(end + 1, idx)
            )
            if gap_ok:
                end = idx
            else:
                break
        if end - start >= 1:
            return (start, end)

    # Strategy 2: everything before first non-cover Heading1
    for i, p in enumerate(paragraphs):
        if p.get('paragraph_type') == 'heading1' and p.get('confidence', 0) >= 0.7:
            # Check if the heading text looks like a cover item (university name, etc.)
            text = p.get('text', '').strip()
            if re.search(r'(?:毕业|学位|学士|硕士|博士)论文', text):
                continue
            if re.search(r'(?:本科|研究生)毕业设计', text):
                continue
            if i > 0:
                return (0, i - 1)
            break

    return None


def _extract_cover_fields(paragraphs: list[dict], start: int, end: int) -> dict[str, str]:
    """Extract structured fields from cover page paragraphs.

    Returns a dict mapping field names to their values.
    """
    fields: dict[str, str] = {}

    cover_paragraphs = paragraphs[start:end + 1]

    # Extract title: first large (>=14pt) centered text
    for p in cover_paragraphs:
        text = p.get('text', '').strip()
        if not text:
            continue
        font_size = p.get('font_size_pt', 12)
        alignment = p.get('alignment', 'left')
        if font_size >= 14 and alignment == 'center' and len(text) >= 4:
            # Avoid matching labels (学号, 姓名 etc.)
            if not re.match(r'(?:学\s*号|姓\s*名|院\s*系|专\s*业|指导|辅导|年|月|日)', text):
                fields['title'] = text
                break

    # Extract other fields from text patterns
    for p in cover_paragraphs:
        text = p.get('text', '').strip()
        if not text:
            continue

        for field_name, patterns in _FIELD_PATTERNS.items():
            if field_name in fields:
                continue  # Already found
            for pat in patterns:
                m = pat.search(text)
                if m:
                    value = m.group(1).strip()
                    if value:
                        fields[field_name] = value
                    break

    return fields


def process_cover(doc: dict) -> CoverResult:
    """Analyze a parsed document for cover page presence and extract fields.

    Args:
        doc: The parsed document dict (with 'paragraphs' key).

    Returns:
        CoverResult with detection results and extracted fields.
    """
    paragraphs = doc.get('paragraphs', [])
    if not paragraphs:
        return CoverResult(has_cover=False)

    block = _detect_cover_block(paragraphs)

    if block is None:
        logger.info("No cover page detected")
        return CoverResult(has_cover=False)

    start, end = block
    fields = _extract_cover_fields(paragraphs, start, end)
    logger.info(f"Cover detected: paragraphs [{start}..{end}], fields={list(fields.keys())}")

    return CoverResult(
        has_cover=True,
        cover_start=start,
        cover_end=end,
        fields=fields,
    )
