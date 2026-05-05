"""Pipeline orchestrator — ties together Rust parse → Python classify → Rust assemble."""

from __future__ import annotations
import gc
import json
import logging
import base64
import zipfile
from pathlib import Path
from typing import Optional

import docx_fmt_core  # Rust extension

from app.models import TaskInfo, TaskStatus
from app.config import settings
from app.core.classifier import (
    classify_paragraphs, get_uncertain_indices,
    build_llm_classification_prompt, parse_llm_response,
)
from app.core.llm_client import LLMClient, parse_natural_language_template

logger = logging.getLogger(__name__)

_tasks: dict[str, TaskInfo] = {}


def get_task(task_id: str) -> Optional[TaskInfo]:
    return _tasks.get(task_id)


def create_task(task_id: str) -> TaskInfo:
    task = TaskInfo(task_id=task_id, status=TaskStatus.PENDING, progress=0)
    _tasks[task_id] = task
    return task


def update_task(task_id: str, **kwargs) -> TaskInfo:
    task = _tasks[task_id]
    for k, v in kwargs.items():
        setattr(task, k, v)
    return task


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _resolve_template(template_name, template_docx_path, template_description, llm_client):
    if template_docx_path and template_docx_path.exists():
        from docx import Document
        doc = Document(str(template_docx_path))
        section = doc.sections[0]
        template = json.loads(docx_fmt_core.default_template_json())
        template['page']['margin_top_cm'] = section.top_margin.cm if section.top_margin else 2.54
        template['page']['margin_bottom_cm'] = section.bottom_margin.cm if section.bottom_margin else 2.54
        template['page']['margin_left_cm'] = section.left_margin.cm if section.left_margin else 3.17
        template['page']['margin_right_cm'] = section.right_margin.cm if section.right_margin else 3.17
        template['name'] = 'from_file'
        del doc
        return json.dumps(template, ensure_ascii=False)

    elif template_description and llm_client:
        import asyncio
        loop = asyncio.get_event_loop()
        tpl_dict = loop.run_until_complete(
            parse_natural_language_template(llm_client, template_description)
        )
        if tpl_dict:
            defaults = json.loads(docx_fmt_core.default_template_json())
            _deep_merge(defaults, tpl_dict)
            return json.dumps(defaults, ensure_ascii=False)

    elif template_name:
        template = json.loads(docx_fmt_core.default_template_json())
        template['name'] = template_name
        return json.dumps(template, ensure_ascii=False)

    return docx_fmt_core.default_template_json()


def _extract_image_blobs_as_base64(source_path: Path) -> str:
    blobs = []
    try:
        with zipfile.ZipFile(source_path, 'r') as z:
            idx = 0
            for name in z.namelist():
                if name.startswith('word/media/'):
                    data = z.read(name)
                    blobs.append({"index": idx, "blob_base64": base64.b64encode(data).decode('ascii')})
                    idx += 1
    except Exception as e:
        logger.warning(f"Failed to extract image blobs: {e}")
    return json.dumps(blobs)


async def run_format_pipeline(
    task_id: str,
    source_path: Path,
    template_name: Optional[str] = None,
    template_docx_path: Optional[Path] = None,
    template_description: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
) -> Path:
    output_path = source_path.parent / f"formatted_{source_path.name}"

    try:
        update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="正在解析文档...")
        doc_json = docx_fmt_core.parse_docx(str(source_path))

        update_task(task_id, progress=20, message="正在解析模板...")
        template_json = _resolve_template(template_name, template_docx_path, template_description, llm_client)

        update_task(task_id, status=TaskStatus.CLASSIFYING, progress=35, message="正在识别文档结构...")
        doc = json.loads(doc_json)
        doc['paragraphs'] = classify_paragraphs(doc['paragraphs'])

        if llm_client and settings.llm_enable_classification:
            uncertain = get_uncertain_indices(doc['paragraphs'])
            if uncertain:
                logger.info(f"LLM classifying {len(uncertain)} uncertain paragraphs")
                prompt = build_llm_classification_prompt(doc['paragraphs'], uncertain)
                try:
                    response = await llm_client.classify_paragraphs(prompt)
                    updates = parse_llm_response(response)
                    if updates:
                        doc_json = json.dumps(doc, ensure_ascii=False)
                        doc_json = docx_fmt_core.update_classifications(doc_json, json.dumps(updates))
                        doc = json.loads(doc_json)
                except Exception as e:
                    logger.error(f"LLM classification failed: {e}")

        updates = [{"index": i, "type": p['paragraph_type'], "confidence": p['confidence']}
                    for i, p in enumerate(doc['paragraphs'])]
        doc_json = json.dumps(doc, ensure_ascii=False)
        doc_json = docx_fmt_core.update_classifications(doc_json, json.dumps(updates))

        classification_preview = [
            {"index": i, "type": p['paragraph_type'], "confidence": p['confidence'],
             "text": p['text'][:100]}
            for i, p in enumerate(doc['paragraphs'])
        ]
        update_task(task_id, classification_result=classification_preview)

        update_task(task_id, progress=55, message="正在处理图片...")
        blobs_json = _extract_image_blobs_as_base64(source_path)
        doc_json = docx_fmt_core.set_image_blobs(doc_json, blobs_json)

        update_task(task_id, status=TaskStatus.ASSEMBLING, progress=70, message="正在排版生成文档...")
        docx_fmt_core.assemble_docx(doc_json, template_json, str(output_path))

        del doc
        gc.collect()

        update_task(task_id, status=TaskStatus.COMPLETED, progress=100,
                     message="排版完成", download_url=f"/download/{task_id}")

        logger.info(f"Pipeline completed: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Pipeline failed for task {task_id}: {e}", exc_info=True)
        update_task(task_id, status=TaskStatus.FAILED, progress=0, message=f"处理失败: {str(e)}")
        raise
