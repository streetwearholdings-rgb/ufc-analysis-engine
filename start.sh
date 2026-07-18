#!/bin/sh
set -eu

echo "Running database migrations..."
alembic upgrade head
echo "Database migrations completed successfully."

echo "Starting API server on 0.0.0.0:${PORT:-8000}..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
