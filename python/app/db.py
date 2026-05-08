"""SQLite database — single file, zero-ops storage for templates and redeem codes."""

from __future__ import annotations
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.data_dir) / "docfmt.db"


def _ensure_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist. Idempotent."""
    _ensure_dir()
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS redeem_codes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT UNIQUE NOT NULL,
                total_quota INTEGER NOT NULL,
                used_quota  INTEGER NOT NULL DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now')),
                expires_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                config_json TEXT NOT NULL,
                is_builtin  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS batch_tasks (
                id          TEXT PRIMARY KEY,
                code        TEXT NOT NULL,
                template_id INTEGER,
                status      TEXT DEFAULT 'pending',
                total       INTEGER NOT NULL DEFAULT 0,
                completed   INTEGER NOT NULL DEFAULT 0,
                error_msg   TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS batch_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id    TEXT NOT NULL,
                filename    TEXT NOT NULL,
                task_id     TEXT,
                status      TEXT DEFAULT 'pending',
                error_msg   TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (batch_id) REFERENCES batch_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS llm_call_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     TEXT,
                call_type   TEXT NOT NULL DEFAULT 'chat',
                model       TEXT,
                prompt      TEXT,
                response    TEXT,
                status      TEXT DEFAULT 'success',
                error_msg   TEXT,
                latency_ms  INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_redeem_code ON redeem_codes(code);
            CREATE INDEX IF NOT EXISTS idx_batch_code ON batch_tasks(code);
        """)

        # Seed builtin templates if empty
        count = conn.execute("SELECT COUNT(*) FROM templates WHERE is_builtin = 1").fetchone()[0]
        if count == 0:
            _seed_builtin_templates(conn)

    logger.info(f"Database initialized at {DB_PATH}")


def get_setting(key: str, default: str = "") -> str:
    """Read a setting from the settings table."""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    """Upsert a setting in the settings table."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def insert_llm_log(task_id: Optional[str], call_type: str, model: str, prompt: str,
                     response: str, status: str, error_msg: Optional[str] = None,
                     latency_ms: Optional[int] = None):
    """Insert an LLM call log record."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO llm_call_logs (task_id, call_type, model, prompt, response, status, error_msg, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, call_type, model, prompt, response, status, error_msg, latency_ms),
        )


def list_llm_logs(limit: int = 100, offset: int = 0) -> list[dict]:
    """List recent LLM call logs."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_call_logs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def _seed_builtin_templates(conn: sqlite3.Connection):
    """Insert the hardcoded builtin templates into the database."""
    import json

    builtins = [
        {
            "name": "default",
            "description": "默认学术论文格式",
            "config": _default_template_config(),
        },
        {
            "name": "gb7714",
            "description": "GB/T 7714 参考文献格式",
            "config": _gb7714_config(),
        },
        {
            "name": "thesis_cn",
            "description": "中国学位论文通用格式",
            "config": _thesis_cn_config(),
        },
        {
            "name": "ieee",
            "description": "IEEE Conference Paper Format",
            "config": _ieee_config(),
        },
    ]

    for tpl in builtins:
        conn.execute(
            "INSERT INTO templates (name, description, config_json, is_builtin) VALUES (?, ?, ?, 1)",
            (tpl["name"], tpl["description"], json.dumps(tpl["config"], ensure_ascii=False)),
        )


def _default_template_config() -> dict:
    return {
        "name": "default",
        "description": "默认学术论文格式",
        "page": {
            "page_width_cm": 21.0, "page_height_cm": 29.7,
            "margin_top_cm": 2.54, "margin_bottom_cm": 2.54,
            "margin_left_cm": 3.17, "margin_right_cm": 3.17,
            "header_distance_cm": 1.5, "footer_distance_cm": 1.75,
            "page_number_format": "decimal", "page_number_start": 1,
        },
        "heading1": {"font_name": "SimHei", "font_size_pt": 16, "bold": True, "italic": False, "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 24, "space_after_pt": 18, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "heading2": {"font_name": "SimHei", "font_size_pt": 14, "bold": True, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 12, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "heading3": {"font_name": "SimHei", "font_size_pt": 12, "bold": True, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 6, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "body": {"font_name": "SimSun", "font_size_pt": 12, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 2, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "body_indent": {"font_name": "SimSun", "font_size_pt": 12, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "abstract_style": {"font_name": "SimSun", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 2, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.25, "line_spacing_rule": "multiple"},
        "keywords": {"font_name": "SimHei", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "caption_figure": {"font_name": "SimHei", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 6, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "caption_table": {"font_name": "SimHei", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 6, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "reference": {"font_name": "SimSun", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 0, "hanging_indent_chars": 2, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "quote": {"font_name": "KaiTi", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 2, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "list_item": {"font_name": "SimSun", "font_size_pt": 12, "bold": False, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"},
        "table": {"top_rule_width_pt": 1.5, "mid_rule_width_pt": 0.75, "bottom_rule_width_pt": 1.5, "header_font_name": "SimHei", "header_font_size_pt": 10.5, "header_bold": True, "cell_font_name": "SimSun", "cell_font_size_pt": 10.5, "cell_align": "center", "caption_position": "above", "caption_font_name": "SimHei", "caption_font_size_pt": 10.5},
        "figure": {"max_width_cm": 15.0, "align": "center", "caption_position": "below", "caption_font_name": "SimHei", "caption_font_size_pt": 10.5},
        "references": {"font_name": "SimSun", "font_size_pt": 10.5, "hanging_indent_chars": 2, "spacing_between": 3},
    }


def _gb7714_config() -> dict:
    base = _default_template_config()
    base["name"] = "gb7714"
    base["description"] = "GB/T 7714 参考文献格式"
    base["reference"] = {"font_name": "SimSun", "font_size_pt": 10.5, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 0, "hanging_indent_chars": 3, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.25, "line_spacing_rule": "multiple"}
    base["references"] = {"font_name": "SimSun", "font_size_pt": 10.5, "hanging_indent_chars": 3, "spacing_between": 2}
    return base


def _thesis_cn_config() -> dict:
    base = _default_template_config()
    base["name"] = "thesis_cn"
    base["description"] = "中国学位论文通用格式"
    base["heading1"] = {"font_name": "SimHei", "font_size_pt": 16, "bold": True, "italic": False, "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 24, "space_after_pt": 18, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"}
    base["heading2"] = {"font_name": "SimHei", "font_size_pt": 14, "bold": True, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 12, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"}
    base["heading3"] = {"font_name": "SimHei", "font_size_pt": 12, "bold": True, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 6, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"}
    base["body"] = {"font_name": "SimSun", "font_size_pt": 12, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 2, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.5, "line_spacing_rule": "multiple"}
    return base


def _ieee_config() -> dict:
    base = _default_template_config()
    base["name"] = "ieee"
    base["description"] = "IEEE Conference Paper Format"
    base["page"] = {
        "page_width_cm": 21.59, "page_height_cm": 27.94,
        "margin_top_cm": 1.9, "margin_bottom_cm": 2.54,
        "margin_left_cm": 1.65, "margin_right_cm": 1.65,
        "header_distance_cm": 1.27, "footer_distance_cm": 1.27,
        "page_number_format": "decimal", "page_number_start": 1,
    }
    base["heading1"] = {"font_name": "Times New Roman", "font_size_pt": 12, "bold": True, "italic": False, "alignment": "center", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 12, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.0, "line_spacing_rule": "multiple"}
    base["heading2"] = {"font_name": "Times New Roman", "font_size_pt": 11, "bold": True, "italic": False, "alignment": "left", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 6, "space_after_pt": 6, "line_spacing_pt": None, "line_spacing_multiple": 1.0, "line_spacing_rule": "multiple"}
    base["body"] = {"font_name": "Times New Roman", "font_size_pt": 10, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 0, "hanging_indent_chars": 0, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.0, "line_spacing_rule": "multiple"}
    base["reference"] = {"font_name": "Times New Roman", "font_size_pt": 9, "bold": False, "italic": False, "alignment": "justify", "first_line_indent_chars": 0, "hanging_indent_chars": 2, "space_before_pt": 0, "space_after_pt": 0, "line_spacing_pt": None, "line_spacing_multiple": 1.0, "line_spacing_rule": "multiple"}
    base["references"] = {"font_name": "Times New Roman", "font_size_pt": 9, "hanging_indent_chars": 2, "spacing_between": 2}
    return base
