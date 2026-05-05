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

STRUCTURAL_KEYWORDS = {
    '摘要': 'heading1', 'abstract': 'heading1',
    '关键词': 'heading1', 'keywords': 'heading1',
    '目录': 'heading1', '参考文献': 'heading1', 'references': 'heading1',
    '致谢': 'heading1', '附录': 'heading1',
    '引言': 'heading1', '结论': 'heading1', '绪论': 'heading1',
}

CAPTION_FIG_RE = re.compile(r'^图\s*\d+[-.]\d+')
CAPTION_TAB_RE = re.compile(r'^表\s*\d+[-.]\d+')
REF_RE = re.compile(r'^\[\d+\]')


def _match_pattern(text: str, patterns: list) -> bool:
    return any(p.match(text) for p in patterns)


def classify_one(text: str, font_size: Optional[float], bold: bool,
                 alignment: Optional[str], char_count: int,
                 body_font_size: float) -> tuple[str, float]:
    stripped = text.strip()
    if not stripped or char_count < 2:
        return "body", 0.5

    if CAPTION_FIG_RE.match(stripped):
        return "caption_figure", 0.95
    if CAPTION_TAB_RE.match(stripped):
        return "caption_table", 0.95
    if REF_RE.match(stripped):
        return "reference", 0.85

    lower = stripped.lower()
    for kw, kw_type in STRUCTURAL_KEYWORDS.items():
        if lower == kw or lower.startswith(kw):
            return kw_type, 0.90

    if _match_pattern(stripped, HEADING1_PATS):
        return "heading1", 0.85
    if _match_pattern(stripped, HEADING2_PATS):
        return "heading2", 0.85
    if _match_pattern(stripped, HEADING3_PATS):
        return "heading3", 0.85

    font_ratio = (font_size / body_font_size) if font_size and body_font_size else 1.0
    is_large = font_ratio >= 1.1
    is_short = char_count < 60
    is_centered = alignment == "center"

    score = 0.0
    if is_large: score += 0.3
    if bold: score += 0.25
    if is_centered: score += 0.2
    if is_short: score += 0.15

    if score >= 0.5:
        if font_ratio >= 1.3:
            return "heading1", min(score, 0.90)
        elif font_ratio >= 1.15:
            return "heading2", min(score, 0.85)
        else:
            return "heading3", min(score, 0.80)

    return "body", 0.6


def classify_paragraphs(paragraphs: list[dict]) -> list[dict]:
    sizes = [p['font_size_pt'] for p in paragraphs if p.get('font_size_pt') and p['font_size_pt'] > 0]
    body_font_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0

    for para in paragraphs:
        ptype, conf = classify_one(
            text=para.get('text', ''), font_size=para.get('font_size_pt'),
            bold=para.get('bold', False), alignment=para.get('alignment'),
            char_count=para.get('char_count', 0), body_font_size=body_font_size,
        )
        para['paragraph_type'] = ptype
        para['confidence'] = conf
    return paragraphs


def get_uncertain_indices(paragraphs: list[dict], threshold: float = 0.70) -> list[int]:
    return [i for i, p in enumerate(paragraphs) if p.get('confidence', 0) < threshold]


def build_llm_classification_prompt(paragraphs: list[dict], indices: list[int]) -> str:
    lines = []
    for idx in indices:
        p = paragraphs[idx]
        text = p.get('text', '')[:200]
        lines.append(f"[{idx}] {text}")

    return f"""你是文档结构分析专家。判断以下段落的类型。

类型：heading1, heading2, heading3, body, caption_figure, caption_table, reference, abstract, keywords, quote, list_item

严格输出 JSON 数组：[{{"index": 序号, "type": "类型", "confidence": 0.0-1.0}}]

段落列表：
{chr(10).join(lines)}"""


def parse_llm_response(response: str) -> list[dict]:
    try:
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)
        results = json.loads(json_str)
        valid_types = {"heading1","heading2","heading3","body","body_indent",
                       "caption_figure","caption_table","reference","abstract",
                       "keywords","quote","list_item","code","toc","unknown"}
        return [{"index": i["index"], "type": i["type"], "confidence": float(i.get("confidence", 0.6))}
                for i in results if i.get("type") in valid_types]
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return []
