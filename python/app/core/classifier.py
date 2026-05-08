"""Rule-based paragraph classifier — Python version.

Handles content analysis + format heuristics. Classification results are injected
back into the Rust-parsed document via JSON update calls.
NEVER modifies paragraph text.
"""

from __future__ import annotations
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HEADING1_PATS = [
    re.compile(r'^第[一二三四五六七八九十百千\d]+[章节部篇]'),
    re.compile(r'^\d{1,2}\s+\S'),
]
HEADING2_PATS = [
    re.compile(r'^\d{1,2}\.\d{1,2}\s+\S'),
    re.compile(r'^[（(][一二三四五六七八九十]+[）)]'),
]
HEADING3_PATS = [
    re.compile(r'^\d{1,2}\.\d{1,2}\.\d{1,2}\s+\S'),
    re.compile(r'^[（(]\d{1,2}[）)]'),
    re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]'),
]

# Content-based role detection — used alongside formatting, never alone
CONTENT_ROLE_PATS: dict[str, list[re.Pattern]] = {
    'abstract': [re.compile(r'^摘\s*要$'), re.compile(r'^Abstract$', re.I)],
    'keywords': [re.compile(r'^关键词[：:]'), re.compile(r'^Keywords[：:]', re.I)],
    'reference': [re.compile(r'^\[\d+\]')],
    'caption_figure': [re.compile(r'^图\s*\d+[-.]\d+')],
    'caption_table': [re.compile(r'^表\s*\d+[-.]\d+')],
    'appendix': [re.compile(r'^附录\s*[A-Z\d]'), re.compile(r'^Appendix\s*[A-Z\d]', re.I)],
    'formula': [re.compile(r'^\(\d+[-.]\d+\)'), re.compile(r'^（\d+[-.]\d+）')],
    'cover': [
        re.compile(r'(?:毕业|学位|学士|硕士|博士)论文', re.I),
        re.compile(r'(?:本科|研究生)毕业设计'),
        re.compile(r'^\S{2,}(?:大学|学院|研究院)'),
        re.compile(r'(?:指导|辅导)教师[：:]'),
        re.compile(r'(?:学\s*号|姓\s*名|院\s*系|专\s*业)[：:]'),
    ],
}

# Paragraph style names that map directly to roles (from w:pStyle in the docx)
STYLE_NAME_TO_ROLE: dict[str, str] = {
    'Heading 1': 'heading1', 'Heading 2': 'heading2', 'Heading 3': 'heading3',
    'heading1': 'heading1', 'heading2': 'heading2', 'heading3': 'heading3',
    '标题 1': 'heading1', '标题 2': 'heading2', '标题 3': 'heading3',
    '标题1': 'heading1', '标题2': 'heading2', '标题3': 'heading3',
    'Title': 'heading1', 'Subtitle': 'heading2',
    'TOC Heading': 'toc',
    'Quote': 'quote', '引用': 'quote',
    'List Bullet': 'list_item', 'List Number': 'list_item',
}


def _match_pattern(text: str, patterns: list) -> bool:
    return any(p.match(text) for p in patterns)


def _match_content_role(text: str) -> Optional[str]:
    """Check if text matches a known content pattern."""
    for role, patterns in CONTENT_ROLE_PATS.items():
        if any(p.match(text) for p in patterns):
            return role
    return None


def _style_name_to_role(style_name: Optional[str]) -> Optional[str]:
    """Map a paragraph style name to a semantic role."""
    if not style_name:
        return None
    return STYLE_NAME_TO_ROLE.get(style_name)


def _format_similarity(para: dict, style: dict) -> float:
    """Score how well a paragraph's formatting matches a template style definition.

    Returns 0.0-1.0. Higher = better match.
    """
    score = 0.0
    checks = 0

    # Font size match (most reliable signal)
    psize = para.get('font_size_pt')
    ssize = style.get('font_size_pt')
    if psize and ssize:
        checks += 1
        diff = abs(psize - ssize)
        if diff <= 0.5:
            score += 1.0
        elif diff <= 1.0:
            score += 0.7
        elif diff <= 2.0:
            score += 0.3

    # Bold match
    pbold = para.get('bold', False)
    sbold = style.get('bold', False)
    if sbold is not None:
        checks += 1
        if pbold == sbold:
            score += 1.0
        elif sbold and not pbold:
            score += 0.0  # style says bold, para isn't
        else:
            score += 0.5  # para is bold but style doesn't require it

    # Alignment match
    palign = para.get('alignment')
    salign = style.get('alignment')
    if palign and salign:
        checks += 1
        if palign == salign:
            score += 1.0
        else:
            score += 0.0

    # First line indent match
    pindent = para.get('is_first_line_indent', False)
    sindent = style.get('first_line_indent_chars', 0)
    checks += 1
    if pindent and sindent and sindent > 0:
        score += 1.0
    elif not pindent and (not sindent or sindent == 0):
        score += 1.0
    else:
        score += 0.0

    return score / checks if checks > 0 else 0.0


def classify_one(text: str, font_size: Optional[float], bold: bool,
                 alignment: Optional[str], char_count: int,
                 body_font_size: float,
                 paragraph_style_name: Optional[str] = None,
                 is_first_line_indent: bool = False,
                 space_before_pt: Optional[float] = None,
                 line_spacing: Optional[float] = None,
                 style_map: Optional[dict] = None) -> tuple[str, float]:
    stripped = text.strip()
    if not stripped or char_count < 2:
        return "body", 0.5

    # ── Step 1: Check paragraph style name ────────────────────────
    role_from_style = _style_name_to_role(paragraph_style_name)
    if role_from_style:
        return role_from_style, 0.90

    # ── Step 2: Content pattern matching ──────────────────────────
    content_role = _match_content_role(stripped)
    if content_role:
        # Content match gives a tentative role, but verify with formatting
        # e.g., "摘要" in a heading font should be abstract, not heading1
        if style_map and content_role in style_map:
            tpl_style = style_map[content_role]
            sim = _format_similarity({
                'font_size_pt': font_size, 'bold': bold,
                'alignment': alignment, 'is_first_line_indent': is_first_line_indent,
            }, tpl_style)
            # If formatting roughly matches the template style, use it
            if sim >= 0.3:
                return content_role, 0.85
        # Even without template style, content patterns for these are reliable
        if content_role in ('abstract', 'keywords', 'reference', 'caption_figure', 'caption_table', 'appendix', 'formula', 'cover'):
            return content_role, 0.80

    # ── Step 3: Heading pattern matching ──────────────────────────
    if _match_pattern(stripped, HEADING1_PATS):
        return "heading1", 0.85
    if _match_pattern(stripped, HEADING2_PATS):
        return "heading2", 0.85
    if _match_pattern(stripped, HEADING3_PATS):
        return "heading3", 0.85

    # ── Step 4: Template style matching (if available) ────────────
    if style_map:
        best_role = None
        best_score = 0.0
        para_props = {
            'font_size_pt': font_size, 'bold': bold,
            'alignment': alignment, 'is_first_line_indent': is_first_line_indent,
        }
        for role, tpl_style in style_map.items():
            sim = _format_similarity(para_props, tpl_style)
            if sim > best_score:
                best_score = sim
                best_role = role

        if best_role and best_score >= 0.80:
            return best_role, min(best_score, 0.90)

    # ── Step 5: Heuristic scoring (fallback) ──────────────────────
    font_ratio = (font_size / body_font_size) if font_size and body_font_size else 1.0
    is_large = font_ratio >= 1.1
    is_short = char_count < 60
    is_very_short = char_count < 30
    is_centered = alignment == "center"

    score = 0.0
    if is_large: score += 0.3
    if bold: score += 0.2
    if is_centered: score += 0.2
    if is_short: score += 0.15
    if is_very_short: score += 0.05

    threshold = 0.5
    if char_count >= 200:
        threshold = 0.75
    elif char_count >= 100:
        threshold = 0.65
    elif char_count >= 60:
        threshold = 0.60
    else:
        threshold = 0.65

    if score >= threshold:
        if font_ratio >= 1.3:
            return "heading1", min(score, 0.90)
        elif font_ratio >= 1.15:
            return "heading2", min(score, 0.85)
        else:
            return "heading3", min(score, 0.80)

    return "body", 0.6


def classify_paragraphs(paragraphs: list[dict], style_map: Optional[dict] = None) -> list[dict]:
    sizes = [p['font_size_pt'] for p in paragraphs if p.get('font_size_pt') and p['font_size_pt'] > 0]
    body_font_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0

    for para in paragraphs:
        ptype, conf = classify_one(
            text=para.get('text', ''), font_size=para.get('font_size_pt'),
            bold=para.get('bold', False), alignment=para.get('alignment'),
            char_count=para.get('char_count', 0), body_font_size=body_font_size,
            paragraph_style_name=para.get('paragraph_style_name'),
            is_first_line_indent=para.get('is_first_line_indent', False),
            space_before_pt=para.get('space_before_pt'),
            line_spacing=para.get('line_spacing'),
            style_map=style_map,
        )
        para['paragraph_type'] = ptype
        para['confidence'] = conf
    return paragraphs


def get_uncertain_indices(paragraphs: list[dict], threshold: float = 0.80) -> list[int]:
    return [i for i, p in enumerate(paragraphs) if p.get('confidence', 0) < threshold]


def build_llm_classification_prompt(paragraphs: list[dict], indices: list[int]) -> str:
    """Build a prompt that includes 1 neighbor before/after each uncertain paragraph.

    Neighbors are included as context but NOT marked with '?' — the LLM should only
    classify the paragraphs with '?' markers.
    """
    lines = []
    for idx in indices:
        # Previous neighbor (1 paragraph)
        if idx > 0:
            prev_text = paragraphs[idx - 1].get('text', '')[:120]
            lines.append(f"[{idx - 1}] {prev_text}")
        # Current uncertain paragraph
        text = paragraphs[idx].get('text', '')[:200]
        lines.append(f"[{idx}] ? {text}")
        # Next neighbor (1 paragraph)
        if idx < len(paragraphs) - 1:
            next_text = paragraphs[idx + 1].get('text', '')[:120]
            lines.append(f"[{idx + 1}] {next_text}")
        lines.append("")  # blank separator

    return f"""你是文档结构分析专家。判断每个标记了 ? 的段落类型。

类型：heading1, heading2, heading3, body, caption_figure, caption_table, reference, abstract, keywords, quote, list_item, cover, appendix, formula, unknown
（如果无法确定类型请使用 unknown）

严格输出 JSON 数组：[{{"index": 序号, "type": "类型", "confidence": 0.0-1.0}}]
只输出标记了 ? 的段落，未标记的不要出现在结果中。

段落列表：
{chr(10).join(lines)}"""


def parse_llm_response(response: str) -> tuple[list[dict], Optional[str]]:
    """Parse LLM classification response. Returns (results, error_reason).

    results: list of classification dicts (empty on failure)
    error_reason: None if successful, otherwise describes why parsing failed
    """
    if not response or not response.strip():
        return [], "LLM returned empty response"

    json_str = response.strip()

    # ── Strategy 1: Direct JSON parse ──
    # Try to parse the whole response as JSON first
    try:
        results = json.loads(json_str)
        if isinstance(results, list):
            valid = _filter_valid_types(results)
            if valid:
                return valid, None
            return [], "JSON array contained no valid paragraph types"
        elif isinstance(results, dict) and "classifications" in results:
            valid = _filter_valid_types(results["classifications"])
            if valid:
                return valid, None
    except (json.JSONDecodeError, ValueError):
        pass

    # ── Strategy 2: Extract JSON from code blocks ──
    for pattern in [r'```(?:json)?\s*([\[\{].*?[\]\}])\s*```', r'```\s*([\[\{].*?[\]\}])\s*```']:
        m = re.search(pattern, json_str, re.DOTALL)
        if m:
            try:
                results = json.loads(m.group(1))
                if isinstance(results, list):
                    valid = _filter_valid_types(results)
                    if valid:
                        return valid, None
                elif isinstance(results, dict) and "classifications" in results:
                    valid = _filter_valid_types(results["classifications"])
                    if valid:
                        return valid, None
            except (json.JSONDecodeError, ValueError):
                continue

    # ── Strategy 3: Find JSON array in the text ──
    # Look for the outermost JSON array using bracket matching
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        start = json_str.find(start_char)
        if start < 0:
            continue
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(json_str)):
            c = json_str[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    candidate = json_str[start:i + 1]
                    try:
                        results = json.loads(candidate)
                        if isinstance(results, list):
                            valid = _filter_valid_types(results)
                            if valid:
                                return valid, None
                        elif isinstance(results, dict):
                            if "classifications" in results:
                                valid = _filter_valid_types(results["classifications"])
                                if valid:
                                    return valid, None
                            # Maybe it's a single object, wrap in list
                            if "index" in results and "type" in results:
                                valid = _filter_valid_types([results])
                                if valid:
                                    return valid, None
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    # ── Strategy 4: Try to find individual JSON objects with regex ──
    obj_pattern = re.compile(r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"type"\s*:\s*"(\w+)"[^}]*\}')
    matches = obj_pattern.findall(json_str)
    if matches:
        valid_types = {"heading1","heading2","heading3","body","body_indent",
                       "caption_figure","caption_table","reference","abstract",
                       "keywords","quote","list_item","code","toc",
                       "cover","appendix","formula","unknown"}
        results = []
        for m in matches:
            idx, ptype = int(m[0]), m[1]
            if ptype in valid_types:
                results.append({"index": idx, "type": ptype, "confidence": 0.6})
        if results:
            return results, None

    preview = response[:300]
    return [], f"无法从LLM响应中解析JSON (响应长度={len(response)}): {preview}"


def _filter_valid_types(results: list[dict]) -> list[dict]:
    """Filter results to only include valid paragraph types."""
    valid_types = {"heading1","heading2","heading3","body","body_indent",
                   "caption_figure","caption_table","reference","abstract",
                   "keywords","quote","list_item","code","toc",
                   "cover","appendix","formula","unknown"}
    filtered = []
    for item in results:
        if not isinstance(item, dict):
            continue
        ptype = item.get("type")
        if ptype not in valid_types:
            continue
        try:
            idx = int(item.get("index", -1))
        except (TypeError, ValueError):
            continue
        if idx < 0:
            continue
        try:
            conf = float(item.get("confidence", 0.6))
        except (TypeError, ValueError):
            conf = 0.6
        filtered.append({"index": idx, "type": ptype, "confidence": conf})
    return filtered
