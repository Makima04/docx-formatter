"""Pydantic models for the Python API layer."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


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
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLASSIFYING = "classifying"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str = ""
    download_url: Optional[str] = None
    classification_result: Optional[list[dict]] = None


class ClassificationUpdate(BaseModel):
    index: int
    type: str
    confidence: float = 0.0
