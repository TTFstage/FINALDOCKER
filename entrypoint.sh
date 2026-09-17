#!/bin/bash
set -e

# Set default values if not defined
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"

echo "[INFO] Initializing container startup..."

# Pass the password to pg_isready to avoid authentication issues
export PGPASSWORD="${DB_PASSWORD}"

# Wait for the database with a maximum timeout (30 seconds)
MAX_RETRIES=30
RETRY_COUNT=0

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[ERROR] Unable to connect to PostgreSQL at $DB_HOST:$DB_PORT after $MAX_RETRIES attempts. Aborting."
        exit 1
    fi
    echo "[WAIT] PostgreSQL not ready yet ($RETRY_COUNT/$MAX_RETRIES)... waiting 1s"
    sleep 1
done

echo "[OK] PostgreSQL is up and responding at $DB_HOST:$DB_PORT."

# Run database migrations with Flask-Migrate
echo "[MIGRATE] Running 'flask db upgrade'..."
flask db upgrade

# Start the application by replacing the shell process with Gunicorn (PID 1)
echo "[START] Starting Gunicorn with 4 workers on 0.0.0.0:8000..."
exec gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app