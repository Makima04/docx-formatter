"""Pipeline orchestrator — ties together Rust parse → Python classify → Rust assemble."""

from __future__ import annotations
import gc
import json
import logging
import base64
import tempfile
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
from app.core.template_analyzer import TemplateAnalyzer
from app.core.cover_engine import process_cover
from app.core.layout_planner import LayoutPlanner
from app.core.style_registry import StyleRegistry
from app.core.renderer import PDFRenderer
from app.core.validator import LayoutValidator
from app.core.repair_engine import RepairEngine
from app.core.trace import FormattingTrace

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


def _style_map_from_template_config(tpl: dict) -> dict:
    """Build a style_map from a TemplateConfig dict for use by the classifier.

    Maps each paragraph role to its formatting properties so the classifier
    can compare paragraph formatting against template definitions.
    """
    ROLE_KEYS = [
        "heading1", "heading2", "heading3", "body", "body_indent",
        "abstract_style", "keywords", "caption_figure", "caption_table",
        "reference", "quote", "list_item",
    ]
    ROLE_NAME_MAP = {
        "abstract_style": "abstract",
    }
    style_map = {}
    for key in ROLE_KEYS:
        section = tpl.get(key)
        if not section or not isinstance(section, dict):
            continue
        role = ROLE_NAME_MAP.get(key, key)
        line_rule = section.get("line_spacing_rule", "multiple")
        style_map[role] = {
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
            "line_spacing_rule": line_rule,
        }
    return style_map


def _resolve_template(template_name, template_docx_path, template_description, llm_client):
    """Returns (template_json_str, style_map_or_None)."""
    if template_docx_path and template_docx_path.exists():
        analyzer = TemplateAnalyzer(str(template_docx_path))
        profile = analyzer.analyze()
        tpl_config = profile["template_config"]
        style_map = profile.get("style_map", {})
        logger.info(f"Template analyzed: quality={profile['quality_score']}, "
                    f"roles={list(style_map.keys())}")
        return json.dumps(tpl_config, ensure_ascii=False), style_map

    elif template_description and llm_client:
        import asyncio
        loop = asyncio.get_event_loop()
        tpl_dict = loop.run_until_complete(
            parse_natural_language_template(llm_client, template_description)
        )
        if tpl_dict:
            defaults = json.loads(docx_fmt_core.default_template_json())
            _deep_merge(defaults, tpl_dict)
            style_map = _style_map_from_template_config(defaults)
            return json.dumps(defaults, ensure_ascii=False), style_map

    elif template_name:
        template = json.loads(docx_fmt_core.default_template_json())
        template['name'] = template_name
        style_map = _style_map_from_template_config(template)
        return json.dumps(template, ensure_ascii=False), style_map

    defaults = json.loads(docx_fmt_core.default_template_json())
    style_map = _style_map_from_template_config(defaults)
    return json.dumps(defaults, ensure_ascii=False), style_map


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
    trace = FormattingTrace(task_id)

    try:
        # ── Stage 1: Parse ──
        update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="正在解析文档...")
        doc_json = docx_fmt_core.parse_docx(str(source_path))
        doc = json.loads(doc_json)
        trace.record("parse", {"paragraphs": len(doc.get("paragraphs", [])),
                               "tables": len(doc.get("tables", [])),
                               "images": len(doc.get("images", []))})

        # ── Stage 2: Template ──
        update_task(task_id, progress=20, message="正在解析模板...")
        template_json, style_map = _resolve_template(template_name, template_docx_path, template_description, llm_client)
        tpl_dict = json.loads(template_json)
        trace.record("template_analysis", {"template_name": tpl_dict.get("name", "default"),
                                           "has_style_map": style_map is not None})

        # ── Stage 3: Classify ──
        total_paras = len(doc['paragraphs'])
        update_task(task_id, status=TaskStatus.CLASSIFYING, progress=35,
                    message=f"正在识别文档结构 (0/{total_paras})...")

        # Classify with progress updates
        sizes = [p['font_size_pt'] for p in doc['paragraphs']
                 if p.get('font_size_pt') and p['font_size_pt'] > 0]
        body_font_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0
        from app.core.classifier import classify_one

        for i, para in enumerate(doc['paragraphs']):
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
            # Update progress every 10 paragraphs
            if (i + 1) % 10 == 0 or i == total_paras - 1:
                pct = 35 + int((i + 1) / total_paras * 15)  # 35% → 50%
                update_task(task_id, progress=pct,
                            message=f"正在识别文档结构 ({i + 1}/{total_paras})...")

        if llm_client and settings.llm_enable_classification:
            uncertain = get_uncertain_indices(doc['paragraphs'])
            if uncertain:
                update_task(task_id, progress=50,
                            message=f"正在用 AI 识别 {len(uncertain)} 个不确定段落...")
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
        doc = json.loads(doc_json)

        classification_preview = [
            {"index": i, "type": p['paragraph_type'], "confidence": p['confidence'],
             "text": p['text'][:100]}
            for i, p in enumerate(doc['paragraphs'])
        ]
        update_task(task_id, classification_result=classification_preview)
        trace.record("classification", {"total": len(doc['paragraphs']),
                                        "uncertain_count": len(get_uncertain_indices(doc['paragraphs']))})

        # ── Stage 4: Images ──
        update_task(task_id, progress=55, message="正在处理图片...")
        blobs_json = _extract_image_blobs_as_base64(source_path)
        doc_json = docx_fmt_core.set_image_blobs(doc_json, blobs_json)
        doc = json.loads(doc_json)

        # ── Stage 5: Cover detection ──
        update_task(task_id, progress=60, message="正在分析封面...")
        cover_result = process_cover(doc)
        if cover_result.has_cover:
            logger.info(f"Cover detected: fields={list(cover_result.fields.keys())}, "
                        f"range=[{cover_result.cover_start}..{cover_result.cover_end}]")
        trace.record("cover_detection", {"has_cover": cover_result.has_cover,
                                         "fields": list(cover_result.fields.keys())})

        # ── Stage 6: Layout plan ──
        update_task(task_id, progress=65, message="正在生成排版计划...")
        registry = StyleRegistry.from_template_config(tpl_dict)
        planner = LayoutPlanner(doc, tpl_dict, registry)
        layout_plan = planner.plan()
        layout_plan_dict = layout_plan.model_dump()
        plan_json = layout_plan.model_dump_json()
        trace.record("layout_plan", {
            "table_placements": len(layout_plan_dict.get("table_placements", [])),
            "figure_plans": len(layout_plan_dict.get("figure_plans", [])),
            "formula_plans": len(layout_plan_dict.get("formula_plans", [])),
        })

        # ── Stage 7: Initial assembly ──
        update_task(task_id, status=TaskStatus.ASSEMBLING, progress=70, message="正在排版生成文档...")
        docx_fmt_core.assemble_docx_with_plan(doc_json, template_json, str(output_path), plan_json)
        trace.record("assembly", {"output": str(output_path), "iteration": 0})

        # ── Stage 8: Validation & Repair loop ──
        if settings.enable_pdf_validation:
            renderer = PDFRenderer(settings.libreoffice_path, settings.pdf_dpi)
            validator = LayoutValidator()
            repair_engine = RepairEngine()

            for iteration in range(settings.max_repair_iterations):
                # Render to PDF
                update_task(task_id, status=TaskStatus.RENDERING, progress=72,
                            message=f"正在渲染 PDF (第{iteration + 1}轮)...")
                with tempfile.TemporaryDirectory() as tmp_dir:
                    pdf_path = renderer.render_to_pdf(str(output_path), tmp_dir)
                    if not pdf_path:
                        logger.info("LibreOffice not available, skipping PDF validation")
                        break

                    # Validate
                    update_task(task_id, status=TaskStatus.VALIDATING, progress=75,
                                message=f"正在验证排版 (第{iteration + 1}轮)...")
                    layout_data = renderer.extract_layout(pdf_path)
                    report = validator.validate(layout_data, doc, tpl_dict)
                    trace.record("validation", {
                        "iteration": iteration + 1,
                        "passed": report.passed,
                        "issues": [{"id": i.issue_id, "severity": i.severity.value,
                                    "message": i.message} for i in report.issues],
                    })

                    if report.passed:
                        logger.info(f"Validation passed on iteration {iteration + 1}")
                        update_task(task_id, validation_report=report.model_dump())
                        break

                    # Repair
                    update_task(task_id, status=TaskStatus.REPAIRING, progress=78,
                                message=f"正在自动修复 (第{iteration + 1}轮)...")
                    actions = repair_engine.generate_repairs(report, layout_plan_dict, doc, tpl_dict)
                    if not actions:
                        logger.info(f"No repair actions for iteration {iteration + 1}")
                        update_task(task_id, validation_report=report.model_dump())
                        break

                    layout_plan_dict, tpl_dict = repair_engine.apply_repairs(
                        actions, layout_plan_dict, tpl_dict)
                    trace.record("repair", {
                        "iteration": iteration + 1,
                        "actions": [{"type": a.action_type, "target": a.target_index,
                                     "risk": a.risk_level} for a in actions],
                    })

                    # Re-assemble with repaired plan
                    plan_json = json.dumps(layout_plan_dict, ensure_ascii=False)
                    template_json = json.dumps(tpl_dict, ensure_ascii=False)
                    docx_fmt_core.assemble_docx_with_plan(
                        doc_json, template_json, str(output_path), plan_json)
                    trace.record("assembly", {"output": str(output_path),
                                              "iteration": iteration + 1})

                    update_task(task_id, validation_report=report.model_dump())

        # ── Complete ──
        del doc
        gc.collect()

        update_task(task_id, status=TaskStatus.COMPLETED, progress=100,
                     message="排版完成", download_url=f"/download/{task_id}",
                     formatting_trace=trace.to_dict())

        logger.info(f"Pipeline completed: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Pipeline failed for task {task_id}: {e}", exc_info=True)
        update_task(task_id, status=TaskStatus.FAILED, progress=0, message=f"处理失败: {str(e)}",
                     formatting_trace=trace.to_dict())
        raise
