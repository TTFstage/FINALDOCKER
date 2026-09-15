# ==========================================
# STAGE 1: Builder (Compilazione e Dipendenze)
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installa strumenti di compilazione
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Crea una cartella "wheels" con tutti i pacchetti già compilati
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# ==========================================
# STAGE 2: Immagine Finale di Runtime
# ==========================================
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installa solo le dipendenze di runtime (libpq5 invece di libpq-dev, postgresql-client se necessario)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa i pacchetti compilati dallo stage precedente
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir /wheels/*

# Copia il codice dell'applicazione
COPY . .

# Crea un utente non-root e imposta i permessi sui file
RUN useradd -m -u 1000 appuser && \
    chmod +x entrypoint.sh && \
    chown -R appuser:appuser /app

# Passa all'utente sicuro
USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]