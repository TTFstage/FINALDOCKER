#!/bin/bash
set -e

# Aspetta che il database PostgreSQL sia pronto prima di procedere
# Questo è opzionale ma consigliato
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"

# Esegui le migrazioni del database
echo "Running flask db upgrade..."
flask db upgrade

# Avvia l'applicazione con gunicorn
echo "Starting Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
