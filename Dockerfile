FROM python:3.12-slim

# Imposta la directory di lavoro
WORKDIR /app

# Installa dipendenze di sistema utili
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copia i requisiti e installali
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY . .

# Rendi eseguibile lo script di entrypoint
RUN chmod +x entrypoint.sh

# Esponi la porta usata da gunicorn
EXPOSE 8000

# Definisce l'entrypoint per eseguire le migrazioni e avviare l'app
ENTRYPOINT ["./entrypoint.sh"]
