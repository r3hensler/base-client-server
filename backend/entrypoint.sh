#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"

# Use uvicorn directly for dev (--reload doesn't work with gunicorn+uvicorn workers)
# Use gunicorn with uvicorn workers for production (dual-stack IPv6+IPv4 socket)
if [[ " $* " == *" --reload "* ]]; then
  exec uvicorn app.main:app --host "0.0.0.0" --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}" "$@"
else
  exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b "[::]:${PORT:-8000}" --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}" "$@"
fi
