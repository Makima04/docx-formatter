# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Docx Formatter — automated document formatting tool that parses .docx files, classifies paragraph structure (headings, body, references, etc.), and reassembles them with consistent formatting. Rust + Python hybrid architecture.

## Build & Run

**Create and activate Python virtual environment (always use venv):**
```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
```

**Install Python dependencies:**
```bash
pip install -r python/requirements.txt
```

**Build the Rust extension (required before running, must be inside venv):**
```bash
maturin develop --release        # local dev (installs into active venv)
maturin build --release          # production wheel → target/wheels/
```

**Run the server:**
```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

**Run frontend (dev mode, proxies API to :8000):**
```bash
cd frontend && npm install && npm run dev
```

**Docker (full stack):**
```bash
docker compose up --build
```

Environment variables are prefixed with `DOCFMT_` (e.g., `DOCFMT_LLM_API_KEY`). See `python/app/config.py` for all settings.

## Architecture

### Data Pipeline

```
.docx file
  → Rust parse_docx()        [streaming XML → ExtractedDocument JSON]
  → Python classify_paragraphs()  [rule-based + LLM fallback]
  → Python LLM reclassify     [optional, for low-confidence paragraphs]
  → Rust assemble_docx()      [ExtractedDocument JSON + TemplateConfig JSON → new .docx]
```

Rust and Python communicate entirely via JSON strings across the PyO3 boundary. The contract is defined by structs in `engine/src/models.rs`.

### Rust Engine (`engine/`)

- **parser.rs** — Streaming docx parser using quick-xml. Reads `word/document.xml` as XML events, extracts paragraphs/tables without DOM. Memory-efficient (constant per-paragraph).
- **assembler.rs** — Builds a complete .docx zip package from `ExtractedDocument` + `TemplateConfig`. All XML is generated from scratch (no template copying).
- **xml_utils.rs** — All raw OOXML XML generation lives here. Unit conversions: cm→emu, pt→half-points, pt→twips.
- **models.rs** — Shared data models (the JSON contract). `ExtractedDocument`, `TemplateConfig`, `ParagraphStyle`, `PageStyle`, etc.
- **py_bindings.rs** — PyO3 module `docx_fmt_core` exposing 5 functions: `parse_docx`, `assemble_docx`, `update_classifications`, `default_template_json`, `set_image_blobs`.

### Python Backend (`python/`)

- **app/api/main.py** — FastAPI app. Core endpoints: `POST /api/format` (single file, requires X-Redeem-Code header), `GET /api/tasks/{id}`, `GET /download/{id}`. Also mounts the React SPA as static files with client-side routing fallback.
- **app/api/templates.py** — Template CRUD: `GET/POST /api/templates`, `GET/PUT/DELETE /api/templates/{id}`. Builtin templates are seeded from db.py; custom templates are user-created.
- **app/api/redeem.py** — Redeem code endpoints: `POST /api/redeem/check`, `GET/POST /api/redeem/admin/codes`.
- **app/api/batch.py** — Batch processing: `POST /api/batch`, `GET /api/batch/{id}`, `GET /api/batch/{id}/download` (zip).
- **app/core/pipeline.py** — Orchestrates the full pipeline. Task state is held in an in-memory `_tasks` dict (not persistent across restarts).
- **app/core/classifier.py** — Rule-based paragraph classification using regex patterns and font heuristics. Chinese academic document conventions (第X章, 摘要, 参考文献, etc.).
- **app/core/llm_client.py** — OpenAI-compatible API client for two purposes: (1) classifying uncertain paragraphs, (2) parsing natural language template descriptions into `TemplateConfig` JSON.
- **app/core/redeem.py** — Redeem code validation, quota consume/refund.
- **app/core/batch.py** — Batch task orchestrator. Creates batch records in SQLite, processes files concurrently respecting the worker semaphore.
- **app/db.py** — SQLite database initialization. Tables: `redeem_codes`, `templates`, `batch_tasks`, `batch_items`. Seeds 4 builtin templates on first run.
- **app/config.py** — Pydantic settings loaded from env vars with `DOCFMT_` prefix.
- **app/models.py** — Python-side Pydantic models mirroring the Rust types.

### Frontend (`frontend/`)

React + Vite + TypeScript SPA. Pages: Login (redeem code entry), Home (single file format), Batch (multi-file), Templates (CRUD), History (localStorage).

- Vite dev server proxies `/api` and `/download` to backend at `:8000`.
- In production, the built `dist/` is served by FastAPI as static files (SPA fallback).
- History and redeem code are stored in localStorage (client-side only).

### Key Design Decisions

- Images are lazy-loaded: parser extracts media paths only; blobs are loaded from zip and base64-encoded in Python, then injected via `set_image_blobs`.
- The `_resolve_template` function in pipeline.py handles three template sources: builtin name, uploaded .docx file (extracts page margins), or natural language description (via LLM).
- Task progress is tracked via `TaskStatus` enum: pending → processing → classifying → assembling → completed/failed.
- Classification uses a confidence score; paragraphs below 0.70 are sent to the LLM for re-classification.

## Configuration

All settings via environment variables (prefix `DOCFMT_`):

| Variable | Default | Description |
|---|---|---|
| `DOCFMT_LLM_API_KEY` | None | OpenAI-compatible API key (optional) |
| `DOCFMT_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `DOCFMT_LLM_MODEL` | `gpt-4o-mini` | Model name |
| `DOCFMT_MAX_WORKERS` | 2 | Concurrent task limit |
| `DOCFMT_MAX_UPLOAD_SIZE_MB` | 50 | Max upload file size |
