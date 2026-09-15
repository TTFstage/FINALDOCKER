#!/bin/bash
set -e

# Imposta valori di default se non definiti
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"

echo "[INFO] Inizializzazione avvio contenitore..."

# Passa la password a pg_isready per evitare problemi di autenticazione
export PGPASSWORD="${DB_PASSWORD}"

# Attesa del database con un timeout max (30 secondi)
MAX_RETRIES=30
RETRY_COUNT=0

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[ERROR] Impossibile connettersi a PostgreSQL su $DB_HOST:$DB_PORT dopo $MAX_RETRIES tentativi. Abort."
        exit 1
    fi
    echo "[WAIT] PostgreSQL non è ancora pronto ($RETRY_COUNT/$MAX_RETRIES)... attesa 1s"
    sleep 1
done

echo "[OK] PostgreSQL è attivo e risponde su $DB_HOST:$DB_PORT."

# Esegui le migrazioni del database con Flask-Migrate
echo "[MIGRATE] Esecuzione di 'flask db upgrade'..."
flask db upgrade

# Avvia l'applicazione sostituendo il processo di shell con Gunicorn (PID 1)
echo "[START] Avvio di Gunicorn con 4 worker su 0.0.0.0:8000..."
exec gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app