#!/usr/bin/env bash
# Fly.io backend entrypoint (DEPLOY-02).
#
# Order:
#   1. Run Alembic migrations against DATABASE_URL. Idempotent — a no-op on
#      a warm boot; on cold boot brings the schema up to `head`. Failure
#      here aborts the boot so the app never serves against a stale schema.
#   2. Exec uvicorn with 2 workers on ${PORT:-8080}. `exec` replaces the
#      shell so Fly sees the uvicorn process directly for signals + logs.
set -euo pipefail

# The Fly volume is mounted at /app/data; make sure the subdirs Chroma +
# yfinance expect exist before either library is imported.
mkdir -p "${CHROMA_PATH:-/app/data/chroma}" "${YFINANCE_CACHE_PATH:-/app/data/price_cache}"

echo "[entrypoint] running alembic upgrade head"
python -m alembic upgrade head

echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT:-8080} (workers=2)"
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips="*"
