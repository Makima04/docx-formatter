"""Configuration — loaded from environment variables."""

from __future__ import annotations
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Docx Formatter"
    debug: bool = False

    data_dir: str = "/data"
    upload_dir: str = "/data/uploads"
    output_dir: str = "/data/outputs"
    max_upload_size_mb: int = 50

    cors_origins: str = "*"  # comma-separated origins for CORS

    max_workers: int = 2
    task_timeout_sec: int = 300

    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_enable_classification: bool = True
    llm_enable_template_parse: bool = True

    model_config = {"env_prefix": "DOCFMT_", "env_file": ".env"}


settings = Settings()
