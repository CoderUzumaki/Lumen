# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Lumen backend — Fly.io deploy image (DEPLOY-02)
#
# Base: python:3.11-slim (matches the dev interpreter in HANDOFF).
# Entrypoint: `scripts/entrypoint.sh` runs `alembic upgrade head` then
# starts uvicorn with 2 workers on port 8080 (Fly's default internal port).
# The sentence-transformers embedding model is pre-downloaded during build
# so the first request doesn't stall on a ~90MB pull.
# ---------------------------------------------------------------------------

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface \
    PORT=8080

# System deps:
# - build-essential + libpq-dev: psycopg2-binary is bundled but numpy /
#   sentence-transformers still need a compiler for optional native paths.
# - curl: /health probe from the Fly platform.
# - libgomp1: sentence-transformers pulls in torch which needs libgomp at
#   runtime on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgomp1 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so the pip layer caches across code changes.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Bake the embedding model into the image so the first request doesn't
# spend 5–10s pulling ~90MB from Hugging Face. Uses the same model id
# Config.EMBEDDING_MODEL defaults to.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# App code.
COPY . .

# Non-root user for the runtime process. `app` owns /app so the entrypoint
# can chmod / mkdir under the Fly volume mount at /app/data on first boot.
RUN useradd --create-home --uid 1001 --shell /bin/bash app \
    && mkdir -p /app/data \
    && chmod +x /app/scripts/entrypoint.sh \
    && chown -R app:app /app
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
