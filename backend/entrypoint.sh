#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}" "$@"
