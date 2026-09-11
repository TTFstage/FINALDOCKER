---
# 🚀 Infrastructure & Docker Optimization Changelog

Questo documento dettaglia il refactoring dell'infrastruttura Docker, della gestione della rete, degli script di avvio e del reverse proxy Nginx per il progetto.
---

## 📋 Indice

1. [Dockerfile (Flask Application)](https://www.google.com/search?q=%231-dockerfile-flask-application)
2. [Docker Compose Architecture](https://www.google.com/search?q=%232-docker-compose-architecture)
3. [Entrypoint Script (`entrypoint.sh`)](https://www.google.com/search?q=%233-entrypoint-script-entrypointsh)
4. [Nginx Reverse Proxy (`nginx.conf`)](https://www.google.com/search?q=%234-nginx-reverse-proxy-nginxconf)
5. [Tabella Comparativa Prima vs Dopo](https://www.google.com/search?q=%235-tabella-comparativa-prima-vs-dopo)

---

## 1. Dockerfile (Flask Application)

### 🔴 Criticità Precedenti

- **Esecuzione come Root:** Il container eseguiva l'applicazione con privilegi di `root`, esponendo il sistema a rischi di sicurezza in caso di vulnerabilità remote.
- **Dipendenze di Build in Runtime:** Pacchetti come `gcc` e `libpq-dev` rimanevano nell'immagine finale, aumentando inutilmente le dimensioni dell'immagine e la superficie di attacco.
- **Buffering dei Log:** Mancava la variabile per disabilitare il buffering dell'I/O Python, causando ritardi nella visualizzazione dei log su `stdout/stderr`.

### 🟢 Modifiche e Soluzioni

- **Multi-Stage Build:**
- **Stage 1 (`builder`):** Compila i pacchetti e genera le wheel (`.whl`) per le dipendenze Python con C-extensions.
- **Stage 2 (`runtime`):** Copia solo le wheel compilate e le librerie C dinamiche strettamente necessarie (`libpq5`).

- **Non-Root User:** Creato un utente di sistema `appuser` (UID 1000) per l'esecuzione del processo Flask/Gunicorn.
- **Environment Flags:** Aggiunte `PYTHONUNBUFFERED=1` (log istantanei nei container) e `PYTHONDONTWRITEBYTECODE=1` (previene la creazione di file `.pyc`).

---

## 2. Docker Compose Architecture

### 🔴 Criticità Precedenti

- **Race Condition al Boot:** I servizi `web` e `gps_worker` dipendevano da `db` con `condition: service_started`. Poiché PostgreSQL impiega alcuni secondi per essere operativo, l'applicazione andava in crash all'avvio.
- **Esposizione Database all'Esterno:** La porta `5432:5432` era mappata su tutte le interfacce dell'host (`0.0.0.0`), esponendo il DB a potenziale traffico esterno non autorizzato.
- **Rete Non Isolata:** Tutti i microservizi condividevano un'unica rete di default.

### 🟢 Modifiche e Soluzioni

- **Healthchecks Generici:**
- Implementati healthcheck nativi per **PostgreSQL** (`pg_isready`), **Redis** (`redis-cli ping`) e **RabbitMQ** (`rabbitmq-diagnostics`).
- Aggiornati i vincoli `depends_on` con `condition: service_healthy` per azzerare i crash al boot.

- **Segregazione delle Reti (Network Isolation):**
- **`frontend`**: Comunicazione esclusiva tra Nginx, l'app Web (Flask) e l'app FastAPI.
- **`backend`**: Comunicazione isolata tra servizi applicativi, database, Redis e RabbitMQ. Nginx **non** può accedere direttamente al database o ai worker.

- **Hardening Porta Database:** Binding del database limitato a `127.0.0.1:5432:5432` (accesso sicuro solo da localhost per debug/DBeaver) o rimozione totale della mappatura delle porte in produzione.
- **Dry-ENV Config:** Introdotta la direttiva `env_file: - .env` per evitare ridondanze nel file Compose.

---

## 3. Entrypoint Script (`entrypoint.sh`)

### 🔴 Criticità Precedenti

- **Ciclo d'Attesa Infinito:** Se il database non rispondeva (es. credenziali errate), lo script entrava in un loop indefinito senza fare fail-fast.
- **Autenticazione `pg_isready`:** Invocazione di `pg_isready` senza esplicitare le credenziali/password di connessione.

### 🟢 Modifiche e Soluzioni

- **Attesa con Timeout (Fail-Fast):** Aggiunto un limite massimo di tentativi (30 tentativi / 30 secondi). Se il DB non risponde entro il limite, lo script termina con codice di errore `1`.
- **Autenticazione Sicura:** Passata la variabile `PGPASSWORD="${DB_PASSWORD}"` durante la verifica con `pg_isready`.
- **Mantenimento di `exec`:** Confermato l'uso di `exec gunicorn ...` per garantire che Gunicorn assuma il **PID 1** e riceva correttamente i segnali di stop (`SIGTERM`/`SIGINT`) gestiti da Docker.

---

## 4. Nginx Reverse Proxy (`nginx.conf`)

### 🔴 Criticità Precedenti

- **Truncate URL su `proxy_pass`:** Invocazioni come `proxy_pass http://fastapi_backend/stream;` provocavano la riscrittura o il troncamento errato delle rotte sub-path.
- **Header `Connection` Hardcodato:** Impostare staticamente `Connection "upgrade"` su `/stream` corrompeva le normali richieste HTTP non-WebSocket (es. SSE o chiamate REST).
- **Mancanza di Caching Handshake SSL e HTTP/2:** Nessuna cache per i ticket TLS, causando overhead di CPU ad ogni connessione dei client mobili/sensoristici.

### 🟢 Modifiche e Soluzioni

- **Riscrittura Rotte Proxy:** Corrette le direttive in `proxy_pass http://fastapi_backend;` mantenendo l'URI originale inviata dal client.
- **Gestione Dinamica WebSocket (`map` directive):**

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

```

L'header `Connection` ora scala automaticamente tra `upgrade` (per WebSockets) e `close` (per normali chiamate HTTP).

- **Hardening & Performance TLS:**
- Abilitata la direttiva `http2 on`.
- Configurato `ssl_session_cache shared:SSL:10m;` e `ssl_session_timeout 1d;`.
- Aggiunto header **HSTS** (`Strict-Transport-Security`).

---

## 5. Tabella Comparativa Prima vs Dopo

| Componente                 | Stato Iniziale               | Stato Ottimizzato                      | Beneficio                               |
| -------------------------- | ---------------------------- | -------------------------------------- | --------------------------------------- |
| **Dockerfile Security**    | Utente `root`                | Utente unprivileged `appuser`          | Minore impatto da exploit RCE           |
| **Immagine Docker**        | Dipendenze di build incluse  | Multi-stage build                      | Immagine più leggera e pulita           |
| **Orchestrazione Compose** | `condition: service_started` | `condition: service_healthy`           | Zero race condition o crash al boot     |
| **Isolamento Rete**        | Singola rete globale         | Reti separate (`frontend` / `backend`) | Prevenzione accessi diretti al DB       |
| **Nginx WebSockets**       | Header statico               | Mappatura dinamica con `map`           | Supporto 100% per REST + WS + SSE       |
| **TLS/SSL Overhead**       | Handshake ad ogni richiesta  | Cache sessione SSL (`10m`) + HTTP/2    | CPU ridotta sui server e minori latenze |
