#!/usr/bin/env bash
set -euo pipefail

readonly max_attempts=5
readonly retry_delay_seconds=3

echo "Applying database migrations..."
for attempt in $(seq 1 "$max_attempts"); do
    if alembic upgrade head; then
        echo "Database migrations completed successfully."
        break
    fi

    if (( attempt == max_attempts )); then
        echo "Database migrations failed after ${max_attempts} attempts; stopping startup." >&2
        exit 1
    fi

    echo "Database migration attempt ${attempt}/${max_attempts} failed; retrying in ${retry_delay_seconds}s." >&2
    sleep "$retry_delay_seconds"
done

echo "Starting API server."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
