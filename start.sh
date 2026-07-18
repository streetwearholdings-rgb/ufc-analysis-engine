#!/usr/bin/env bash
set -euo pipefail

echo "Applying database migrations..."

max_attempts=5
attempt=1

until alembic upgrade head; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Database migrations failed after ${max_attempts} attempts." >&2
        exit 1
    fi

    echo "Migration attempt ${attempt} failed; retrying in 5 seconds..." >&2
    attempt=$((attempt + 1))
    sleep 5
done

echo "Database migrations completed."
echo "Starting UFC Analysis API..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
