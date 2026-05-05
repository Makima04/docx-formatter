#!/usr/bin/env bash
# Quick-start script: create venv, install deps, build Rust extension
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -q -r python/requirements.txt

echo "Building Rust extension (maturin develop --release)..."
pip install -q maturin
maturin develop --release

echo ""
echo "Done! To start the server:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.api.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "To start the frontend (dev mode):"
echo "  cd frontend && npm install && npm run dev"
