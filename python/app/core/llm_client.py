"""LLM client — handles classification fallback + natural language template parsing."""

from __future__ import annotations
import json
import re
import time
import logging
from typing import Optional

import httpx
from app.db import insert_llm_log

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o-mini", timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(self, prompt: str, system: str = "", temperature: float = 0.1,
                   use_json_format: bool = True,
                   call_type: str = "chat", task_id: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if use_json_format:
            payload["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if not content or not content.strip():
                    raise ValueError("LLM returned empty content")
                latency_ms = int((time.perf_counter() - start) * 1000)
                insert_llm_log(task_id, call_type, self.model, prompt, content, "success", None, latency_ms)
                return content
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            insert_llm_log(task_id, call_type, self.model, prompt, "", "failed", str(e), latency_ms)
            raise

    async def classify_paragraphs(self, prompt: str, task_id: Optional[str] = None) -> str:
        # Most providers handle JSON-instruction prompts fine without json_object format.
        # json_object format is unreliable with many providers (they return mixed content).
        json_prompt = prompt + "\n\n请严格输出合法 JSON 数组，不要包含任何其他文本或 markdown 代码块标记。"
        return await self.chat(json_prompt, temperature=0.05, use_json_format=False,
                               call_type="classify", task_id=task_id)


_TEMPLATE_PARSE_PROMPT = """你是文档排版专家。用户用自然语言描述了一个排版模板需求，请将其解析为结构化 JSON。

输出格式（严格遵守 schema）：
```json
{{
  "name": "模板名称",
  "description": "描述",
  "page": {{
    "page_width_cm": 21.0, "page_height_cm": 29.7,
    "margin_top_cm": 2.54, "margin_bottom_cm": 2.54,
    "margin_left_cm": 3.17, "margin_right_cm": 3.17,
    "header_distance_cm": 1.5, "footer_distance_cm": 1.75,
    "page_number_format": "decimal", "page_number_start": 1
  }},
  "heading1": {{
    "font_name": "SimHei", "font_size_pt": 16, "bold": true, "italic": false,
    "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0,
    "space_before_pt": 24, "space_after_pt": 18,
    "line_spacing_pt": null, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"
  }},
  ...其他字段同结构...
  "table": {{
    "top_rule_width_pt": 1.5, "mid_rule_width_pt": 0.75, "bottom_rule_width_pt": 1.5,
    "header_font_name": "SimHei", "header_font_size_pt": 10.5, "header_bold": true,
    "cell_font_name": "SimSun", "cell_font_size_pt": 10.5, "cell_align": "center",
    "caption_position": "above", "caption_font_name": "SimHei", "caption_font_size_pt": 10.5
  }},
  "figure": {{
    "max_width_cm": 15.0, "align": "center", "caption_position": "below",
    "caption_font_name": "SimHei", "caption_font_size_pt": 10.5
  }},
  "references": {{
    "font_name": "SimSun", "font_size_pt": 10.5,
    "hanging_indent_chars": 2, "spacing_between": 3
  }}
}}
```

中文常用字号：初号=42, 小初=36, 一号=26, 小一=24, 二号=22, 小二=18, 三号=16, 小三=15, 四号=14, 小四=12, 五号=10.5, 小五=9
alignment: "left" | "center" | "right" | "justify"
未提到的字段用合理默认值。只输出 JSON。

用户的模板描述：
{description}"""


async def parse_natural_language_template(llm_client: LLMClient, description: str) -> dict:
    prompt = _TEMPLATE_PARSE_PROMPT.format(description=description)
    try:
        response = await llm_client.chat(prompt, system="你是一个 JSON 输出助手。只输出合法 JSON。")
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Failed to parse NL template: {e}")
        return {}
