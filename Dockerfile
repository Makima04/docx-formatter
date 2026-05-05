# ==============================
# Stage 0: Build frontend
# ==============================
FROM node:20-alpine AS frontend-builder

COPY frontend/ /build/
WORKDIR /build
RUN npm ci && npm run build

# ==============================
# Stage 1: Build Rust extension
# ==============================
FROM rust:1.85-bookworm AS rust-builder

RUN apt-get update && apt-get install -y python3-dev python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages maturin[patchelf]

WORKDIR /build
COPY engine/ engine/
COPY pyproject.toml .

RUN maturin build --release --out /wheels

# ==============================
# Stage 2: Python runtime
# ==============================
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY python/ python/
COPY --from=rust-builder /wheels /wheels
COPY --from=frontend-builder /build/dist/ /app/python/static/

RUN pip install --no-cache-dir /wheels/*.whl && \
    pip install --no-cache-dir -r python/requirements.txt && \
    rm -rf /wheels

ENV PYTHONPATH=/app/python
ENV DOCFMT_HOST=0.0.0.0
ENV DOCFMT_PORT=8000
ENV DOCFMT_DATA_DIR=/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
