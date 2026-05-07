"""Pydantic models for the Python API layer."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ParagraphType(str, Enum):
    HEADING1 = "heading1"
    HEADING2 = "heading2"
    HEADING3 = "heading3"
    BODY = "body"
    BODY_INDENT = "body_indent"
    CAPTION_FIGURE = "caption_figure"
    CAPTION_TABLE = "caption_table"
    REFERENCE = "reference"
    QUOTE = "quote"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    CODE = "code"
    LIST_ITEM = "list_item"
    TOC = "toc"
    COVER = "cover"
    APPENDIX = "appendix"
    FORMULA = "formula"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLASSIFYING = "classifying"
    ASSEMBLING = "assembling"
    RENDERING = "rendering"
    VALIDATING = "validating"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str = ""
    download_url: Optional[str] = None
    classification_result: Optional[list[dict]] = None
    validation_report: Optional[dict] = None
    formatting_trace: Optional[dict] = None


class ClassificationUpdate(BaseModel):
    index: int
    type: str
    confidence: float = 0.0


# ── Layout Plan models (Phase 4) ────────────────────────────────────


class TablePlacement(BaseModel):
    table_index: int
    after_para_index: int
    include_caption: bool = False


class TablePlan(BaseModel):
    table_index: int
    col_widths_twips: list[int]
    three_line: bool = True


class FigurePlan(BaseModel):
    image_index: int
    caption_para_index: int
    width_emu: int
    height_emu: int


class FormulaPlan(BaseModel):
    para_index: int
    chapter: int
    number: int


class LayoutPlan(BaseModel):
    table_placements: list[TablePlacement] = []
    table_plans: list[TablePlan] = []
    figure_plans: list[FigurePlan] = []
    formula_plans: list[FormulaPlan] = []


# ── Validation & Repair models (Phase 5) ────────────────────────────


class SeverityLevel(str, Enum):
    P0_CORRUPT = "p0_corrupt"
    P1_STRUCTURAL = "p1_structural"
    P2_LAYOUT = "p2_layout"
    P3_STYLE = "p3_style"
    P4_CONVENTION = "p4_convention"


class ValidationIssue(BaseModel):
    issue_id: str
    severity: SeverityLevel
    message: str
    page_number: Optional[int] = None
    para_index: Optional[int] = None
    target_type: Optional[str] = None
    auto_fixable: bool = True


class ValidationReport(BaseModel):
    passed: bool
    issues: list[ValidationIssue] = []
    metrics: dict = {}
    rendered_pages: int = 0


class RepairAction(BaseModel):
    action_type: str
    target_index: Optional[int] = None
    parameters: dict = {}
    risk_level: str = "low"


# ── Rule & Confirmation models (Phase 6) ────────────────────────────


class FormatRule(BaseModel):
    id: str
    source: str = "natural_language"
    target: str
    constraint: str
    priority: int = 5
    auto_fix: bool = True
    validation_method: str = "visual"
    requires_user_confirmation: bool = False
    repair_strategy: Optional[str] = None
    status: str = "active"


class ConfirmationItem(BaseModel):
    id: str
    category: str
    description: str
    options: list[dict] = []
    risk_level: str = "low"
    auto_resolved: bool = False
    user_choice: Optional[str] = None


# ── Trace model (Phase 7) ───────────────────────────────────────────


class TraceEntry(BaseModel):
    stage: str
    timestamp: str = ""
    data: dict = {}


class FormattingTrace(BaseModel):
    task_id: str
    entries: list[TraceEntry] = []
