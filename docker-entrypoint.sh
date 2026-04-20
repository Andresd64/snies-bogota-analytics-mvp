#!/bin/bash
set -euo pipefail

# Wait until PostgreSQL is available
echo "Checking database connectivity..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "Postgres is up - executing pipeline"

exec python -m app.main
