"""Style Registry — maps semantic roles to OpenXML style IDs.

Builds a role → styleId mapping from template analysis or TemplateConfig.
Handles missing styles by deriving from the nearest matching role's formatting.

Usage:
    registry = StyleRegistry.from_style_map(style_map)
    registry = StyleRegistry.from_template_config(template_config_dict)
    style_id = registry.get_style_id("heading1")  # "Heading1"
    style = registry.get_style("heading1")         # {"font_name": "SimHei", ...}
"""

from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Fixed role → OpenXML styleId mapping (must match engine/assembler.rs)
ROLE_TO_STYLE_ID: dict[str, str] = {
    "heading1": "Heading1",
    "heading2": "Heading2",
    "heading3": "Heading3",
    "body": "Normal",
    "body_indent": "BodyIndent",
    "abstract": "Abstract",
    "keywords": "Keywords",
    "caption_figure": "CaptionFigure",
    "caption_table": "CaptionTable",
    "reference": "Reference",
    "quote": "Quote",
    "list_item": "ListItem",
    "cover": "Heading1",
    "appendix": "Heading1",
    "formula": "Normal",
    "toc": "Normal",
    "code": "Normal",
}

# Fallback chain: when a role has no style definition, try these in order
_FALLBACK_CHAIN: dict[str, list[str]] = {
    "body_indent": ["body"],
    "cover": ["heading1", "body"],
    "appendix": ["heading1", "body"],
    "formula": ["body"],
    "code": ["body"],
    "toc": ["heading1", "body"],
}


class StyleRegistry:
    """Maps semantic paragraph roles to style IDs and formatting properties."""

    def __init__(self, role_map: dict[str, dict]):
        self._role_map = role_map

    @classmethod
    def from_style_map(cls, style_map: dict[str, dict]) -> "StyleRegistry":
        """Build from a TemplateAnalyzer's style_map (role → formatting dict)."""
        return cls(dict(style_map))

    @classmethod
    def from_template_config(cls, tpl: dict) -> "StyleRegistry":
        """Build from a TemplateConfig JSON dict (from Rust default_template_json).

        Extracts formatting properties for each role key and builds the mapping.
        """
        ROLE_KEYS = {
            "heading1": "heading1",
            "heading2": "heading2",
            "heading3": "heading3",
            "body": "body",
            "body_indent": "body_indent",
            "abstract_style": "abstract",
            "keywords": "keywords",
            "caption_figure": "caption_figure",
            "caption_table": "caption_table",
            "reference": "reference",
            "quote": "quote",
            "list_item": "list_item",
        }

        role_map: dict[str, dict] = {}
        for tpl_key, role in ROLE_KEYS.items():
            section = tpl.get(tpl_key)
            if section and isinstance(section, dict):
                role_map[role] = {
                    "source": "template_config",
                    "font_name": section.get("font_name"),
                    "font_size_pt": section.get("font_size_pt"),
                    "bold": section.get("bold", False),
                    "italic": section.get("italic", False),
                    "alignment": section.get("alignment"),
                    "first_line_indent_chars": section.get("first_line_indent_chars", 0),
                    "hanging_indent_chars": section.get("hanging_indent_chars", 0),
                    "space_before_pt": section.get("space_before_pt"),
                    "space_after_pt": section.get("space_after_pt"),
                    "line_spacing_pt": section.get("line_spacing_pt"),
                    "line_spacing_multiple": section.get("line_spacing_multiple"),
                    "line_spacing_rule": section.get("line_spacing_rule", "multiple"),
                }

        return cls(role_map)

    def get_style_id(self, role: str) -> str:
        """Get the OpenXML style ID for a semantic role."""
        return ROLE_TO_STYLE_ID.get(role, "Normal")

    def get_style(self, role: str) -> Optional[dict]:
        """Get the formatting properties for a role, with fallback resolution."""
        style = self._role_map.get(role)
        if style:
            return style

        # Try fallback chain
        for fallback_role in _FALLBACK_CHAIN.get(role, []):
            style = self._role_map.get(fallback_role)
            if style:
                logger.debug(f"Role '{role}' not found, using fallback '{fallback_role}'")
                return style

        return None

    def has_role(self, role: str) -> bool:
        """Check if a role has a style definition (directly or via fallback)."""
        return self.get_style(role) is not None

    def registered_roles(self) -> list[str]:
        """List all roles with direct style definitions."""
        return list(self._role_map.keys())

    def missing_roles(self) -> list[str]:
        """List expected roles that have no style definition."""
        expected = set(ROLE_TO_STYLE_ID.keys())
        registered = set(self._role_map.keys())
        # Exclude roles that can be resolved via fallback
        missing = []
        for role in expected - registered:
            if not any(self._role_map.get(fb) for fb in _FALLBACK_CHAIN.get(role, [])):
                missing.append(role)
        return sorted(missing)
