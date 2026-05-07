"""Template Analyzer — parses template .docx files and generates TemplateConfig.

Analyzes user-uploaded template documents to extract:
1. Style definitions (from styles.xml via python-docx)
2. Page settings (from section properties)
3. Content patterns (paragraph text + formatting)
4. Implicit style clusters (similar formatting groups)
5. A TemplateConfig derived from the template's actual formatting
"""

from __future__ import annotations
import re
import logging
from typing import Optional
from collections import defaultdict

from docx import Document
from docx.shared import Pt, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

# ── Style name → semantic role mapping ─────────────────────────────────

STYLE_NAME_TO_ROLE: dict[str, str] = {
    # Chinese
    '标题 1': 'heading1', '标题 2': 'heading2', '标题 3': 'heading3',
    '标题1': 'heading1', '标题2': 'heading2', '标题3': 'heading3',
    '正文': 'body', 'Body Text': 'body',
    '摘要': 'abstract', 'Abstract': 'abstract',
    '关键词': 'keywords', 'Keywords': 'keywords',
    '图题': 'caption_figure', 'Figure Caption': 'caption_figure',
    '表题': 'caption_table', 'Table Caption': 'caption_table',
    '参考文献': 'reference', 'Bibliography': 'reference',
    'Quote': 'quote', '引用': 'quote',
    'List Bullet': 'list_item', '列表': 'list_item',
    'TOC Heading': 'toc',
    # English
    'Heading 1': 'heading1', 'Heading 2': 'heading2', 'Heading 3': 'heading3',
    'Normal': 'body',
    'Subtitle': 'heading2',
    'Title': 'heading1',
}

# Content text patterns → semantic role
CONTENT_ROLE_PATTERNS: dict[str, list[re.Pattern]] = {
    'abstract': [re.compile(r'^摘\s*要'), re.compile(r'^Abstract', re.I)],
    'keywords': [re.compile(r'^关键词'), re.compile(r'^Keywords', re.I)],
    'heading1': [re.compile(r'^第[一二三四五六七八九十百千\d]+[章节部篇]')],
    'reference': [re.compile(r'^\[\d+\]')],
    'caption_figure': [re.compile(r'^图\s*\d+')],
    'caption_table': [re.compile(r'^表\s*\d+')],
    'cover': [
        re.compile(r'(?:毕业|学位|学士|硕士|博士)论文', re.I),
        re.compile(r'(?:本科|研究生)毕业设计'),
        re.compile(r'^\S{2,}(?:大学|学院|研究院)'),
    ],
}


# ── Unit conversion helpers ────────────────────────────────────────────

def _pt(val) -> Optional[float]:
    if val is None:
        return None
    # Length (from python-docx) is a subclass of int and has .pt property.
    # Must check hasattr BEFORE isinstance to avoid returning raw EMU values.
    if hasattr(val, 'pt'):
        return val.pt
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _cm(val) -> Optional[float]:
    if val is None:
        return None
    if hasattr(val, 'cm'):
        return val.cm
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _align_str(val) -> str:
    if val == WD_ALIGN_PARAGRAPH.CENTER:
        return "center"
    if val == WD_ALIGN_PARAGRAPH.RIGHT:
        return "right"
    if val == WD_ALIGN_PARAGRAPH.JUSTIFY:
        return "justify"
    return "left"


def _line_spacing_info(pf) -> tuple[Optional[float], Optional[float], str]:
    """Return (spacing_pt, spacing_multiple, rule) from a ParagraphFormat."""
    rule = "multiple"
    if pf.line_spacing_rule is not None:
        rule = str(pf.line_spacing_rule).rsplit(".", 1)[-1].lower()
        if rule not in ("multiple", "exact", "at_least"):
            rule = "multiple"

    ls = pf.line_spacing
    if ls is None:
        return None, None, "multiple"

    # Length objects (subclass of int) may appear even for "multiple" rule.
    # Always check for .pt first to avoid treating raw EMU as a multiplier.
    if hasattr(ls, 'pt'):
        pt_val = ls.pt
        # For "multiple" rule, convert pt back to multiplier:
        # python-docx gives line spacing as actual pt value even when rule=multiple.
        # We need to figure out the multiplier: multiple = line_spacing_pt / (font_size * 1.2)
        # But we don't have font_size here. Return as pt and let caller handle.
        if rule == "multiple":
            # Store as pt, let the style resolution figure it out
            return pt_val, None, "multiple_as_pt"
        return pt_val, None, rule

    if isinstance(ls, (int, float)):
        val = float(ls)
        # Sanity check: a real multiplier is typically between 0.5 and 5.0
        # If the value is much larger, it's likely an EMU/raw value, not a multiplier
        if rule == "multiple" and val > 10.0:
            # This is probably a raw value, not a true multiplier.
            # Treat as "not set" to avoid generating absurd XML.
            return None, None, "multiple"
        if rule == "multiple":
            return None, val, "multiple"
        return val, None, rule

    return None, None, "multiple"


# ── Core analyzer ──────────────────────────────────────────────────────

class TemplateAnalyzer:
    """Analyzes a template .docx and produces a TemplateProfile + TemplateConfig."""

    def __init__(self, docx_path: str):
        self.path = docx_path
        self.doc = Document(docx_path)

    def analyze(self) -> dict:
        """Full analysis → TemplateProfile dict."""
        page_settings = self._extract_page_settings()
        style_defs = self._extract_style_definitions()
        para_analysis = self._analyze_paragraphs()
        clusters = self._find_implicit_clusters(para_analysis)
        style_map = self._build_style_map(style_defs, para_analysis, clusters)
        quality, reasons = self._rate_quality(style_defs, para_analysis, clusters)
        template_config = self._generate_template_config(page_settings, style_map)

        return {
            "document_type": self._detect_document_type(para_analysis),
            "quality_score": quality,
            "quality_reasons": reasons,
            "page_settings": page_settings,
            "style_definitions": style_defs,
            "paragraph_count": len(para_analysis),
            "content_summary": self._content_summary(para_analysis),
            "style_map": style_map,
            "implicit_clusters": clusters,
            "template_config": template_config,
        }

    # ── Page settings ──────────────────────────────────────────────

    def _extract_page_settings(self) -> dict:
        if not self.doc.sections:
            return {}
        s = self.doc.sections[0]
        return {
            "page_width_cm": _cm(s.page_width),
            "page_height_cm": _cm(s.page_height),
            "margin_top_cm": _cm(s.top_margin),
            "margin_bottom_cm": _cm(s.bottom_margin),
            "margin_left_cm": _cm(s.left_margin),
            "margin_right_cm": _cm(s.right_margin),
            "header_distance_cm": _cm(s.header_distance),
            "footer_distance_cm": _cm(s.footer_distance),
        }

    # ── Style definitions ──────────────────────────────────────────

    def _extract_style_definitions(self) -> list[dict]:
        styles = []
        for style in self.doc.styles:
            # type 1 = WD_STYLE_TYPE.PARAGRAPH
            if style.type != 1:
                continue

            pf = style.paragraph_format
            font = style.font
            fs = _pt(font.size)

            first_indent = None
            hanging = None
            if pf.first_line_indent is not None:
                indent_emu = pf.first_line_indent  # EMU
                # 1 char ≈ font_size/2 pt ≈ font_size * 12700 EMU
                emu_per_char = (fs or 12) * 12700
                if indent_emu < 0:
                    # negative = hanging indent
                    hanging = round(abs(indent_emu) / emu_per_char, 1)
                else:
                    first_indent = round(indent_emu / emu_per_char, 1)

            sp_before, sp_after, ls_rule = _line_spacing_info(pf)
            # line_spacing can be multiple or exact
            ls_mult = None
            ls_pt = None
            if ls_rule == "multiple":
                raw = pf.line_spacing
                if isinstance(raw, (int, float)):
                    val = float(raw)
                    if val <= 10.0:
                        ls_mult = val
                elif hasattr(raw, 'pt'):
                    # Length object with "multiple" rule — treat as pt, convert later
                    ls_pt = raw.pt
            elif ls_rule == "multiple_as_pt":
                ls_pt = sp_before
                ls_rule = "multiple"
            else:
                ls_pt = _pt(pf.line_spacing)

            styles.append({
                "name": style.name,
                "style_id": style.style_id,
                "base_style": style.base_style.name if style.base_style else None,
                "is_builtin": style.builtin,
                "font_name": font.name,
                "font_size_pt": fs,
                "bold": bool(font.bold),
                "italic": bool(font.italic),
                "alignment": _align_str(pf.alignment),
                "first_line_indent_chars": first_indent,
                "hanging_indent_chars": hanging,
                "space_before_pt": _pt(pf.space_before),
                "space_after_pt": _pt(pf.space_after),
                "line_spacing_pt": ls_pt,
                "line_spacing_multiple": ls_mult,
                "line_spacing_rule": ls_rule,
            })

        return styles

    # ── Paragraph analysis ─────────────────────────────────────────

    def _analyze_paragraphs(self) -> list[dict]:
        results = []
        for i, para in enumerate(self.doc.paragraphs):
            text = para.text.strip()
            style_name = para.style.name if para.style else ""

            # First run's direct formatting
            run0 = para.runs[0] if para.runs else None
            font_size = _pt(run0.font.size) if run0 and run0.font.size else None
            font_name = run0.font.name if run0 and run0.font.name else None
            bold = run0.font.bold if run0 and run0.font.bold is not None else None
            italic = run0.font.italic if run0 and run0.font.italic is not None else None

            pf = para.paragraph_format
            alignment = _align_str(pf.alignment)
            sp_before = _pt(pf.space_before)
            sp_after = _pt(pf.space_after)
            first_indent = pf.first_line_indent

            content_role = None
            for role, patterns in CONTENT_ROLE_PATTERNS.items():
                if any(p.match(text) for p in patterns):
                    content_role = role
                    break

            results.append({
                "index": i,
                "text": text[:200],
                "char_count": len(text),
                "style_name": style_name,
                "font_size_pt": font_size,
                "font_name": font_name,
                "bold": bold,
                "italic": italic,
                "alignment": alignment,
                "content_role": content_role,
                "space_before_pt": sp_before,
                "space_after_pt": sp_after,
                "first_line_indent": first_indent,
            })

        return results

    # ── Implicit clusters ──────────────────────────────────────────

    def _find_implicit_clusters(self, para_analysis: list[dict]) -> list[dict]:
        clusters: dict[tuple, list[dict]] = defaultdict(list)
        for para in para_analysis:
            if not para["text"] or para["char_count"] < 2:
                continue
            key = (para["font_size_pt"], para["bold"], para["alignment"])
            clusters[key].append(para)

        result = []
        for (fs, bold, align), paras in clusters.items():
            roles = [p["content_role"] for p in paras if p["content_role"]]
            result.append({
                "font_size_pt": fs,
                "bold": bold,
                "alignment": align,
                "count": len(paras),
                "samples": [p["text"][:60] for p in paras[:5]],
                "content_roles": list(set(roles)),
            })

        result.sort(key=lambda c: c["count"], reverse=True)
        return result

    # ── Style map ──────────────────────────────────────────────────

    def _build_style_map(self, style_defs, para_analysis, clusters) -> dict:
        style_map: dict[str, dict] = {}

        # 1) By style name
        for sdef in style_defs:
            role = STYLE_NAME_TO_ROLE.get(sdef["name"])
            if role and role not in style_map:
                style_map[role] = {
                    "source": "style_name",
                    "style_name": sdef["name"],
                    **{k: sdef[k] for k in (
                        "font_name", "font_size_pt", "bold", "italic", "alignment",
                        "first_line_indent_chars", "hanging_indent_chars",
                        "space_before_pt", "space_after_pt",
                        "line_spacing_pt", "line_spacing_multiple", "line_spacing_rule",
                    )},
                }

        # 2) By content patterns
        content_matches: dict[str, list[dict]] = defaultdict(list)
        for para in para_analysis:
            if para["content_role"]:
                content_matches[para["content_role"]].append(para)

        for role, paras in content_matches.items():
            if role in style_map:
                continue
            sizes = [p["font_size_pt"] for p in paras if p["font_size_pt"]]
            avg_size = sum(sizes) / len(sizes) if sizes else None
            any_bold = any(p["bold"] for p in paras)
            aligns = [p["alignment"] for p in paras]
            common_align = max(set(aligns), key=aligns.count) if aligns else "left"
            p0 = paras[0]

            style_map[role] = {
                "source": "content_pattern",
                "font_name": p0["font_name"],
                "font_size_pt": avg_size,
                "bold": any_bold,
                "italic": False,
                "alignment": common_align,
                "space_before_pt": p0["space_before_pt"],
                "space_after_pt": p0["space_after_pt"],
                "first_line_indent_chars": None,
                "hanging_indent_chars": None,
                "line_spacing_pt": None,
                "line_spacing_multiple": None,
                "line_spacing_rule": "multiple",
            }

        # 3) By implicit clusters
        for cluster in clusters:
            for role in cluster["content_roles"]:
                if role in style_map:
                    continue
                style_map[role] = {
                    "source": "implicit_cluster",
                    "font_name": None,
                    "font_size_pt": cluster["font_size_pt"],
                    "bold": cluster["bold"],
                    "italic": False,
                    "alignment": cluster["alignment"],
                    "space_before_pt": None,
                    "space_after_pt": None,
                    "first_line_indent_chars": None,
                    "hanging_indent_chars": None,
                    "line_spacing_pt": None,
                    "line_spacing_multiple": None,
                    "line_spacing_rule": "multiple",
                }

        return style_map

    # ── TemplateConfig generation ──────────────────────────────────

    def _generate_template_config(self, page_settings: dict, style_map: dict) -> dict:
        ps = page_settings
        return {
            "name": "from_template",
            "description": "从模板文档自动生成",
            "page": {
                "page_width_cm": ps.get("page_width_cm") or 21.0,
                "page_height_cm": ps.get("page_height_cm") or 29.7,
                "margin_top_cm": ps.get("margin_top_cm") or 2.54,
                "margin_bottom_cm": ps.get("margin_bottom_cm") or 2.54,
                "margin_left_cm": ps.get("margin_left_cm") or 3.17,
                "margin_right_cm": ps.get("margin_right_cm") or 3.17,
                "header_distance_cm": ps.get("header_distance_cm") or 1.5,
                "footer_distance_cm": ps.get("footer_distance_cm") or 1.75,
                "page_number_format": "decimal",
                "page_number_start": 1,
            },
            "heading1": self._ps(style_map, "heading1", "SimHei", 16, True, False, "center", 0, 0, 24, 18, 1.5),
            "heading2": self._ps(style_map, "heading2", "SimHei", 14, True, False, "left", 0, 0, 12, 6, 1.5),
            "heading3": self._ps(style_map, "heading3", "SimHei", 12, True, False, "left", 0, 0, 6, 6, 1.5),
            "body": self._ps(style_map, "body", "SimSun", 12, False, False, "justify", 2, 0, 0, 0, 1.5),
            "body_indent": self._ps(style_map, "body_indent", "SimSun", 12, False, False, "justify", 0, 0, 0, 0, 1.5),
            "abstract_style": self._ps(style_map, "abstract", "SimSun", 10.5, False, False, "justify", 2, 0, 0, 0, 1.25),
            "keywords": self._ps(style_map, "keywords", "SimHei", 10.5, False, False, "left", 0, 0, 0, 0, 1.5),
            "caption_figure": self._ps(style_map, "caption_figure", "SimHei", 10.5, False, False, "center", 0, 0, 6, 6, 1.5),
            "caption_table": self._ps(style_map, "caption_table", "SimHei", 10.5, False, False, "center", 0, 0, 6, 6, 1.5),
            "reference": self._ps(style_map, "reference", "SimSun", 10.5, False, False, "justify", 0, 2, 0, 0, 1.5),
            "quote": self._ps(style_map, "quote", "KaiTi", 10.5, False, False, "justify", 2, 0, 0, 0, 1.5),
            "list_item": self._ps(style_map, "list_item", "SimSun", 12, False, False, "left", 0, 0, 0, 0, 1.5),
            "table": {
                "top_rule_width_pt": 1.5, "mid_rule_width_pt": 0.75, "bottom_rule_width_pt": 1.5,
                "header_font_name": "SimHei", "header_font_size_pt": 10.5, "header_bold": True,
                "cell_font_name": "SimSun", "cell_font_size_pt": 10.5, "cell_align": "center",
                "caption_position": "above", "caption_font_name": "SimHei", "caption_font_size_pt": 10.5,
            },
            "figure": {
                "max_width_cm": 15.0, "align": "center", "caption_position": "below",
                "caption_font_name": "SimHei", "caption_font_size_pt": 10.5,
            },
            "references": {
                "font_name": (style_map.get("reference", {}).get("font_name") or "SimSun"),
                "font_size_pt": (style_map.get("reference", {}).get("font_size_pt") or 10.5),
                "hanging_indent_chars": (style_map.get("reference", {}).get("hanging_indent_chars") or 2),
                "spacing_between": 3,
            },
            "toc": {
                "enabled": True,
                "title": "目录",
                "levels": 3,
            },
        }

    def _ps(self, style_map, role, d_font, d_size, d_bold, d_italic, d_align,
            d_first_indent, d_hanging, d_sp_before, d_sp_after, d_ls_mult) -> dict:
        """Build a ParagraphStyle dict, preferring mapped values over defaults."""
        m = style_map.get(role, {})
        return {
            "font_name": m.get("font_name") or d_font,
            "font_size_pt": m.get("font_size_pt") or d_size,
            "bold": m.get("bold") if m.get("bold") is not None else d_bold,
            "italic": m.get("italic") if m.get("italic") is not None else d_italic,
            "alignment": m.get("alignment") or d_align,
            "first_line_indent_chars": m.get("first_line_indent_chars") or d_first_indent,
            "hanging_indent_chars": m.get("hanging_indent_chars") or d_hanging,
            "space_before_pt": m.get("space_before_pt") or d_sp_before,
            "space_after_pt": m.get("space_after_pt") or d_sp_after,
            "line_spacing_pt": m.get("line_spacing_pt"),
            "line_spacing_multiple": m.get("line_spacing_multiple") or d_ls_mult,
            "line_spacing_rule": m.get("line_spacing_rule") or "multiple",
        }

    # ── Quality rating ─────────────────────────────────────────────

    def _rate_quality(self, style_defs, para_analysis, clusters) -> tuple[str, list[str]]:
        reasons: list[str] = []
        score = 0

        # Style completeness
        known_roles = {STYLE_NAME_TO_ROLE.get(s["name"]) for s in style_defs}
        known_roles.discard(None)
        if len(known_roles) >= 5:
            score += 3
            reasons.append(f"样式体系完整，识别到 {len(known_roles)} 个语义角色")
        elif len(known_roles) >= 2:
            score += 2
            reasons.append(f"部分样式明确，识别到 {len(known_roles)} 个语义角色")
        else:
            reasons.append("样式体系不完整，主要依赖直接格式")

        # Content patterns
        content_roles = {p["content_role"] for p in para_analysis if p["content_role"]}
        if len(content_roles) >= 3:
            score += 2
            reasons.append(f"内容结构清晰，识别到 {len(content_roles)} 个内容模式")
        elif content_roles:
            score += 1
            reasons.append("部分内容可识别")

        # Page settings
        if self.doc.sections:
            score += 1
            reasons.append("页面设置已提取")

        # Implicit clusters
        if len(clusters) >= 3:
            score += 1
            reasons.append(f"发现 {len(clusters)} 个格式聚类")

        if score >= 5:
            return "A", reasons
        if score >= 3:
            return "B", reasons
        if score >= 1:
            return "C", reasons
        return "D", reasons

    # ── Helpers ────────────────────────────────────────────────────

    def _detect_document_type(self, para_analysis) -> str:
        roles = {p["content_role"] for p in para_analysis if p["content_role"]}
        if "abstract" in roles and "keywords" in roles:
            return "academic_paper"
        if "reference" in roles:
            return "report"
        return "document"

    def _content_summary(self, para_analysis) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for p in para_analysis:
            if p["content_role"]:
                counts[p["content_role"]] += 1
        return dict(counts)
