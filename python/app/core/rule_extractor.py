"""Rule extractor - LLM-based extraction of formatting rules from natural language."""

from __future__ import annotations
import json
import logging
import re
from typing import Optional

from app.models import FormatRule
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = (
    "You are a document formatting rule analysis assistant. "
    "Extract all formatting rules from the following template description text.\n\n"
    "Each rule contains:\n"
    "- target: object (heading1, heading2, heading3, body, body_indent, abstract, keywords, "
    "caption_figure, caption_table, reference, quote, list_item, table, figure, cover, formula, page)\n"
    "- constraint: specific constraint (e.g. \"font_size:16pt\", \"bold:true\", \"line_spacing:1.5\", "
    "\"alignment:center\", \"font_name:SimHei\")\n"
    "- priority: 1 (highest) to 10 (lowest)\n"
    "- requires_user_confirmation: true if low confidence or high risk\n\n"
    "Template description:\n{description}\n\n"
    "Output a JSON array only:\n"
    '[{{"target":"heading1","constraint":"font_size:16pt","priority":1,"requires_user_confirmation":false}}]\n\n'
    "Output JSON array only, no other text."
)

# Fallback patterns for common NL formatting rules
_RULE_PATTERNS = [
    # Font size
    (r'(heading1?|H1).*?(\d+)\s*(pt|)', 'heading1', 'font_size:{0}pt'),
    (r'(heading2?|H2).*?(\d+)\s*(pt|)', 'heading2', 'font_size:{0}pt'),
    (r'(heading3?|H3).*?(\d+)\s*(pt|)', 'heading3', 'font_size:{0}pt'),
    (r'(body|text).*?(\d+)\s*(pt|)', 'body', 'font_size:{0}pt'),
    (r'(abstract).*?(\d+)\s*(pt|)', 'abstract', 'font_size:{0}pt'),
    # Font name
    (r'(heading|title).*?(SimHei|Hei)', 'heading1', 'font_name:SimHei'),
    (r'(body|text).*?(SimSun|Song)', 'body', 'font_name:SimSun'),
    (r'(abstract).*?(KaiTi|Kai)', 'abstract', 'font_name:KaiTi'),
    # Bold
    (r'(heading|title).*?(bold|Bold)', 'heading1', 'bold:true'),
    # Line spacing
    (r'(line.?spacing|spacing).*?(\d+\.?\d*)\s*x', 'body', 'line_spacing_multiple:{0}'),
    (r'(line.?spacing|spacing).*?(\d+)\s*pt', 'body', 'line_spacing_pt:{0}'),
    # Alignment
    (r'(heading|title).*?(center|Center)', 'heading1', 'alignment:center'),
    (r'(body|text).*?(justify|Justify)', 'body', 'alignment:justify'),
    # Indent
    (r'(first.?line|indent).*?(\d+).*?(char|)', 'body', 'first_line_indent_chars:{0}'),
    # Space
    (r'(space.?before|before).*?(\d+)\s*pt', 'body', 'space_before_pt:{0}'),
    (r'(space.?after|after).*?(\d+)\s*pt', 'body', 'space_after_pt:{0}'),
    # References
    (r'(reference|bibliography).*?(SimSun|Song)', 'reference', 'font_name:SimSun'),
    (r'(reference|bibliography).*?(\d+)\s*(pt|)', 'reference', 'font_size:{0}pt'),
    # Table style
    (r'(table|table).*?(three.?line)', 'table', 'three_line:true'),
    # Cover
    (r'(cover|title.?page).*?(no.?page.?number|no.?number)', 'cover', 'suppress_page_number:true'),
]

# Chinese keyword patterns (used in regex fallback)
_ZH_RULE_PATTERNS = [
    # Font size
    (r'(标题|一级标题|heading1?).*?(\d+)[磅pt号]', 'heading1', 'font_size:{0}pt'),
    (r'(二级标题|heading2?).*?(\d+)[磅pt号]', 'heading2', 'font_size:{0}pt'),
    (r'(三级标题|heading3?).*?(\d+)[磅pt号]', 'heading3', 'font_size:{0}pt'),
    (r'(正文|body).*?(\d+)[磅pt号]', 'body', 'font_size:{0}pt'),
    (r'(摘要|abstract).*?(\d+)[磅pt号]', 'abstract', 'font_size:{0}pt'),
    # Font name
    (r'(标题|heading).*?(黑体|SimHei)', 'heading1', 'font_name:SimHei'),
    (r'(正文|body).*?(宋体|SimSun)', 'body', 'font_name:SimSun'),
    (r'(摘要|abstract).*?(楷体|KaiTi)', 'abstract', 'font_name:KaiTi'),
    # Bold
    (r'(标题|heading).*?加粗', 'heading1', 'bold:true'),
    # Line spacing
    (r'行距.*?(\d+\.?\d*)倍', 'body', 'line_spacing_multiple:{0}'),
    (r'行距.*?(\d+)[磅pt]', 'body', 'line_spacing_pt:{0}'),
    # Alignment
    (r'(标题|heading).*?居中', 'heading1', 'alignment:center'),
    (r'(正文|body).*?两端对齐', 'body', 'alignment:justify'),
    # Indent
    (r'首行缩进.*?(\d+).*?字符', 'body', 'first_line_indent_chars:{0}'),
    # Space
    (r'(段前|before).*?(\d+)[磅pt]', 'body', 'space_before_pt:{0}'),
    (r'(段后|after).*?(\d+)[磅pt]', 'body', 'space_after_pt:{0}'),
    # References
    (r'(参考文献|reference).*?(宋体|SimSun)', 'reference', 'font_name:SimSun'),
    (r'(参考文献|reference).*?(\d+)[磅pt号]', 'reference', 'font_size:{0}pt'),
    # Table style
    (r'表格.*?(三线|three.?line)', 'table', 'three_line:true'),
    # Cover
    (r'封面.*?(无页码|不显示页码|不要页码)', 'cover', 'suppress_page_number:true'),
]

_ALL_PATTERNS = _RULE_PATTERNS + _ZH_RULE_PATTERNS


class RuleExtractor:
    """Extracts structured formatting rules from natural language template descriptions."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    async def extract_rules(self, template_description: str) -> list[FormatRule]:
        """Extract formatting rules from a natural language description.

        Tries LLM extraction first, falls back to regex patterns.
        """
        if not template_description or not template_description.strip():
            return []

        rules: list[FormatRule] = []

        # Try LLM extraction
        if self.llm_client:
            try:
                llm_rules = await self._extract_via_llm(template_description)
                rules.extend(llm_rules)
            except Exception as e:
                logger.warning(f"LLM rule extraction failed: {e}")

        # Always run regex fallback to catch what LLM might miss
        regex_rules = self._extract_via_regex(template_description)
        existing_constraints = {(r.target, r.constraint) for r in rules}
        for rr in regex_rules:
            if (rr.target, rr.constraint) not in existing_constraints:
                rules.append(rr)

        return rules

    async def _extract_via_llm(self, description: str) -> list[FormatRule]:
        """Use LLM to extract structured rules from natural language."""
        import httpx
        prompt = _EXTRACT_PROMPT.format(description=description[:3000])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.llm_client.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.llm_client.api_key}"},
                    json={
                        "model": self.llm_client.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return []

        # Parse JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        json_str = json_match.group(1) if json_match else content.strip()

        try:
            raw_rules = json.loads(json_str)
        except json.JSONDecodeError:
            array_match = re.search(r'\[[\s\S]*\]', json_str)
            if array_match:
                raw_rules = json.loads(array_match.group())
            else:
                logger.warning(f"Failed to parse LLM rule response: {json_str[:200]}")
                return []

        if not isinstance(raw_rules, list):
            return []

        rules = []
        for i, r in enumerate(raw_rules):
            if not isinstance(r, dict):
                continue
            target = r.get("target", "")
            constraint = r.get("constraint", "")
            if not target or not constraint:
                continue
            rules.append(FormatRule(
                id=f"llm_{i}",
                source="natural_language",
                target=target,
                constraint=constraint,
                priority=r.get("priority", 5),
                requires_user_confirmation=r.get("requires_user_confirmation", False),
                status="active" if self._is_known_target(target) else "pending",
            ))

        return rules

    def _extract_via_regex(self, description: str) -> list[FormatRule]:
        """Fallback regex-based rule extraction."""
        rules = []
        for i, (pattern, target, constraint_tpl) in enumerate(_ALL_PATTERNS):
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                groups = match.groups()
                constraint = constraint_tpl
                for j, g in enumerate(groups[1:], 0):
                    if g:
                        constraint = constraint.replace(f"{{{j}}}", g)
                rules.append(FormatRule(
                    id=f"regex_{i}",
                    source="natural_language",
                    target=target,
                    constraint=constraint,
                    priority=3,
                    requires_user_confirmation=False,
                    status="active",
                ))
        return rules

    @staticmethod
    def _is_known_target(target: str) -> bool:
        known = {
            "heading1", "heading2", "heading3", "body", "body_indent",
            "abstract", "keywords", "caption_figure", "caption_table",
            "reference", "quote", "list_item", "table", "figure",
            "cover", "formula", "page", "code", "toc",
        }
        return target in known
