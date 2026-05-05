# docx-formatter

Automated document formatting tool that parses `.docx` files, classifies paragraph structure (headings, body, references, etc.), and reassembles them with consistent formatting.

## Quick Start (一键部署)

```bash
git clone https://github.com/Makima04/docx-formatter.git
cd docx-formatter
chmod +x deploy.sh
./deploy.sh
```

After deployment, open `http://<your-server-ip>:8000` in your browser.

## Architecture

Rust + Python hybrid:
- **Rust** (`engine/`): docx parsing & assembling via PyO3 bindings
- **Python** (`python/app/`): FastAPI backend + paragraph classifier
- **Frontend** (`frontend/`): React + Vite SPA

## Manual Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
maturin develop --release
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

## Docker Compose

```bash
docker compose up --build
```
