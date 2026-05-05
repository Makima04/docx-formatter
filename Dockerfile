# syntax=docker/dockerfile:1
# ==============================
# Stage 0: Build frontend
# ==============================
FROM node:20-alpine AS frontend-builder

WORKDIR /build
# Copy manifests first so npm ci is cached unless deps change
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Then copy source and build
COPY frontend/ ./
RUN npm run build

# ==============================
# Stage 1: Build Rust extension
# ==============================
FROM rust:1.85-bookworm AS rust-builder

RUN apt-get update && apt-get install -y python3-dev python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages maturin[patchelf]

WORKDIR /build
COPY pyproject.toml .
RUN mkdir -p python
COPY engine/Cargo.toml engine/Cargo.lock ./engine/

# Pre-fetch Rust crates so downloads are cached in a layer
RUN cargo fetch --manifest-path engine/Cargo.toml

# Copy real source and build — registry + target are cached via BuildKit mounts
COPY engine/ ./engine/
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/engine/target \
    maturin build --release --out /wheels

# ==============================
# Stage 2: Python runtime
# ==============================
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install Python deps first (cached unless requirements.txt changes)
COPY python/requirements.txt python/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r python/requirements.txt

COPY python/ python/
COPY --from=rust-builder /wheels /wheels
COPY --from=frontend-builder /build/dist/ /app/python/static/

RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

ENV PYTHONPATH=/app/python
ENV DOCFMT_HOST=0.0.0.0
ENV DOCFMT_PORT=8000
ENV DOCFMT_DATA_DIR=/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
