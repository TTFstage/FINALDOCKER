# DOCUMENTAZIONE TECNICA — FLASK TESTING / GPS REAL-TIME PIPELINE

**Versione documento:** 1.0.0  
**Data:** 2025-09-09  
**Autore / Manutentore:** Davide (Project Lead)  
**Status:** Produzione / Docker Compose Orchestrated  

---

## 1. SOMMARIO ESECUTIVO

Il sistema è un'**architettura ibrida Monolite Modulare + Microservizi** che integra:

| Area | Tecnologia chiave | Scopo |
|---|---|---|
| **Web / Auth** | Flask 3.1.3 + Flask-Security-Too 5.8.2 | Gestione utenti, RBAC gruppi, pagine sicure |
| **DB** | PostgreSQL 15-alpine + SQLAlchemy 2.0.52 + psycopg 3.3.4 | Persistenza relazionale |
| **Message Queue** | RabbitMQ 3.13-management | Disaccoppiamento ingestione / elaborazione |
| **Ingestione** | FastAPI (ASGI) | Endpoint `/stream` e `/session/end` |
| **Worker** | Python consumer Pika 1.3.2 | Consumo coda, generazione GPX, scrittura Redis |
| **Cache Real-Time** | Redis 7-alpine (`redis==5.2.1`) | Posizione utente (`position:{user_id}`) con TTL 90 s |
| **Proxy / SSL** | Nginx (Alpine) | Reverse proxy HTTPS, routing `/stream` vs `/groups` |
| **Orchestrazione** | Docker Compose (`docker-compose.yml`) | Multi-service con `depends_on` e volumi nominati |

---

## 2. STACK TECNOLOGICO DETTAGLIATO (TOOL PER TOOL)

| Tool / Libreria | Versione esatta | Ruolo operativo | File di riferimento | Note tecniche |
|---|---|---|---|---|
| **Python** | 3.14 (`Python314`) | Runtime universale | `Dockerfile`, `entrypoint.sh` | Container base `python:3.14-slim` |
| **Flask** | `3.1.3` | Framework web WSGI | `app/__init__.py` | Factory pattern (`create_app`) |
| **Flask-Security-Too** | `5.8.2` | Auth, RBAC, CSRF, hash `bcrypt` | `app/auth/models.py` | `user_datastore` integrato con `db` |
| **Flask-SQLAlchemy** | `3.1.1` | ORM | `extensions.py` (`db`) | `SQLALCHEMY_TRACK_MODIFICATIONS = False` |
| **Flask-Migrate** | `4.1.0` | Migrazioni schema | `migrations/` | `flask db migrate` / `upgrade` |
| **psycopg** | `3.3.4` / `psycopg-binary==3.3.4` | Driver PostgreSQL | `config.py` | URI `postgresql+psycopg://` |
| **FastAPI** | Implicito (`fastapi_app/`) | Ingestione ASGI | `fastapi_app/main.py` | Pydantic `BaseModel` con `@field_validator` |
| **Pika** | `1.3.2` | Client RabbitMQ (Python) | `fastapi_app/main.py`, `gps_worker/worker_consumer.py` | `BlockingConnection`, `basic_publish`, `basic_ack` |
| **Redis** | `7-alpine` (Docker) + `redis==5.2.1` (Python) | Cache / Stream state | `extensions.py`, `gps_worker/` | `decode_responses=True`, `ex=90` |
| **RabbitMQ** | `rabbitmq:3.13-management` | Broker | `docker-compose.yml` | Healthcheck `rabbitmq-diagnostics` |
| **PostgreSQL** | `postgres:15-alpine` | RDBMS | `docker-compose.yml` (`db`) | Volume `postgres_data` |
| **Nginx** | `nginx:alpine` | Reverse proxy / TLS | `nginx/nginx.conf` | Certificati `nginx/certs/` (`fullchain.pem`) |
| **Gunicorn** | `21.2.0` | WSGI server produzione | `wsgi.py`, `entrypoint.sh` | Binding `0.0.0.0:8000` |
| **Jinja2** | `3.1.6` | Template engine | `app/templates/` | Ereditarietà `base.html` |
| **WTForms** | `3.2.2` | Form HTML sicuri | `app/auth/forms.py` | `csrf_token()` integrato |
| **python-dotenv** | `1.2.3` | Caricamento `.env` | `config.py` | `load_dotenv()` |
| **bcrypt** | `5.0.0` | Hashing password | `config.py` (`SECURITY_PASSWORD_HASH`) | Standard `Flask-Security-Too` |

---

## 3. ARCHITETTURA DEI SERVIZI (COMPONENTI VISIBILI)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser / Mobile)                             │
│  • Login / Register (Flask-Security-Too)                                      │
│  • Gruppi (`/groups`) → RBAC (`owner` / `admin` / `member`)                  │
│  • Polling posizione: `GET /groups/{gid}/member/{uid}/position` (8 s)         │
└──────────────────────┬────────────────────────────────────────────────────────┘
                       │ HTTPS (443) → Nginx (proxy)
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  WEB (Flask / Gunicorn)  —  `app/`  —  Port 8000  —  `redis_client`        │
│  • `extensions.py`: `db`, `migrate`, `security`, `csrf`, `redis_client`     │
│  • `group/routes.py`: `member_position()` → `redis_client.get(...)`        │
│  • Template `group/detail.html`: `.member-position` + `<script>poll`         │
└──────────────────────┬────────────────────────────────────────────────────────┘
                       │ RabbitMQ (`telemetry_stream`)
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FASTAPI (`fastapi_app/`)  —  Port 8000 (expose)  —  `RabbitMQPublisher`     │
│  • Endpoint `/stream` → `TelemetryPoint(rider_id=user_id, ...)`             │
│  • `SessionEnd` → chiusura turno → `stream_mgr.close_session()`               │
│  • `rider_id` = `user_id` (stringa coerente con chiave Redis)               │
└──────────────────────┬────────────────────────────────────────────────────────┘
                       │ Message (`type: point` / `session_end`)
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GPS WORKER (`gps_worker/`)  —  Consumer Pika  —  `redis_client`            │
│  • `on_message()` → `stream_mgr.add_point()` → `redis_client.set(...)`     │
│  • Chiave: `position:{user_id}`  —  TTL: `ex=90` (secondi)                  │
│  • `save_shift_metadata()` → PostgreSQL (`rider_shifts`)                    │
│  • `save_fall_event()` → PostgreSQL (`fall_events`)                        │
└──────────────────────┬────────────────────────────────────────────────────────┘
                       │ GPX su disco (`/data/volume_gpx_storage`)
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  REDIS (`redis:6379`)  —  `redis_data` volume                               │
│  • `redis==5.2.1` (client Python) + `redis:7-alpine` (server Docker)        │
│  • `decode_responses=True`  —  Formato chiave: `position:{user_id}`          │
│  • Valore JSON: `{"lat":..., "lon":..., "session_id":"...", "ts":...}`  │
│  • Memoria liberata automaticamente alla scadenza TTL (nessun `DEL` manuale) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. DETTAGLIO PER COMPONENTE

### 4.1 FLASK WEB — `app/`

**File chiave:** `app/__init__.py` (`create_app`)  
**Pattern:** Application Factory  
**Estensioni inizializzate:**

```python
db.init_app(app)           # SQLAlchemy
migrate.init_app(app, db)  # Migrate
csrf.init_app(app)         # CSRF
security.init_app(app, user_datastore, register_form=ExtendedRegisterForm)
redis_client.connection_pool.connection_kwargs.update(
    host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT']
)
```

**Config ambientali (`config.py`):**

| Variabile | Default | Tipo | Uso |
|---|---|---|---|
| `DB_HOST` | `localhost` | `str` | Host PostgreSQL |
| `DB_PORT` | `5432` | `str` | Porta PostgreSQL |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `postgres` / `''` / `testlogin` | `str` | Credenziali DB |
| `REDIS_HOST` | `localhost` | `str` | Host Redis |
| `REDIS_PORT` | `6379` | `int` | Porta Redis |
| `SECRET_KEY` | fallback | `str` | Chiavi sessione |
| `SECURITY_PASSWORD_SALT` | fallback | `str` | Hash `bcrypt` |

**Blueprint registrati:**

| Blueprint | File rotte | URL prefix | Funzione chiave |
|---|---|---|---|
| `core` | `app/core/routes.py` | `/` | Homepage pubblica |
| `auth` | `app/auth/routes.py` | `/auth` | Login, register, `/me`, SOS |
| `group` | `app/group/routes.py` | `/groups` | Creazione, join, RBAC, **posizione GPS** |

---

### 4.2 FASTAPI — `fastapi_app/`

**File chiave:** `fastapi_app/main.py`  
**Server:** ASGI (esposto da Nginx)  
**Modelli Pydantic:**

```python
class TelemetryPoint(BaseModel):
    rider_id: str          # Coincide con user_id (str)
    session_id: str
    lat: float | None = None
    lon: float | None = None
    speed_kmh: float | None = None
    timestamp: float
    is_confirmed_fall: bool = False
    is_cancelled_fall: bool = False

    @field_validator("rider_id", mode="before")
    def _coerce_user_id(cls, v):
        return str(v) if v is not None else v
```

**Endpoint:**

| Metodo | Path | Input | Output | Tool coinvolto |
|---|---|---|---|---|
| `POST` | `/stream` | `list[TelemetryPoint]` | `{"status":"ok","count":N}` | `RabbitMQPublisher` (`pika`) |
| `POST` | `/session/end` | `SessionEnd(user_id, session_id)` | `{"status":"ok"}` | `RabbitMQPublisher` |
| `GET` | `/healthz` | — | `{"status":"ok"}` | Healthcheck interno |

**Nota tecnica:** `rider_id` nel payload è forzato a `str` dal validator. Per coerenza con la chiave Redis (`position:{user_id}`), il client deve inviare `user_id` (intero come stringa, es. `"42"`) nel campo `rider_id`. Questo allinea il worker (`envelope["rider_id"]`) con la route Flask (`user_id`) senza mapping aggiuntivi.

---

### 4.3 GPS WORKER — `gps_worker/`

**File chiave:** `gps_worker/worker_consumer.py`  
**Pattern:** Consumer RabbitMQ con riconnessione automatica (`pika.BlockingConnection`)  
**Dipendenze Python:** `pika==1.3.2`, `psycopg==3.3.4`, `redis==5.2.1`  

**Flusso `on_message`:**

```python
envelope = json.loads(body)
if msg_type == "point":
    stream_mgr.add_point(...)
    if lat is not None and lon is not None:
        redis_client.set(
            f"position:{envelope['rider_id']}",  # user_id
            json.dumps({"lat":..., "lon":..., ...}),
            ex=POSITION_TTL  # 90 s
        )
elif msg_type == "session_end":
    result = stream_mgr.close_session(...)
    save_shift_metadata(..., envelope["rider_id"], ...)  # user_id → DB `rider_shifts`
```

**Tabella PostgreSQL (`rider_shifts`):**

| Colonna | Tipo | Note |
|---|---|---|
| `session_id` | `TEXT` | Chiave sessione turno |
| `user_id` | `TEXT` / `INTEGER` (mappato) | Identificativo utente |
| `gpx_path` | `TEXT` | Percorso file `.gpx` |
| `total_distance_km` | `FLOAT` | Distanza calcolata |
| `duration_min` | `FLOAT` | Durata turno |

**Tabella PostgreSQL (`fall_events`):**

| Colonna | Tipo | Note |
|---|---|---|
| `session_id` | `TEXT` | Sessione associata |
| `user_id` | `TEXT` / `INTEGER` | Utente coinvolto |
| `latitude` | `FLOAT` | Latitudine evento |
| `longitude` | `FLOAT` | Longitudine evento |
| `timestamp` | `TIMESTAMP` | `to_timestamp(timestamp_ms / 1000.0)` |

---

### 4.4 REDIS — Cache Posizione Reale

**Server Docker:** `redis:7-alpine` (`expose: 6379`)  
**Client Python:** `redis==5.2.1` (`extensions.py`)  
**Configurazione (`config.py`):**

```python
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
```

**Inizializzazione (`app/__init__.py`):**

```python
redis_client.connection_pool.connection_kwargs.update(
    host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT']
)
```

**Schema chiave / valore:**

| Elemento | Formato | Esempio | TTL |
|---|---|---|---|
| Chiave | `position:{user_id}` | `position:42` | `ex=90` |
| Valore | JSON stringa | `{"lat":45.0,"lon":9.0,"session_id":"sess_01","ts":1717777777.0}` | Rinnovato a ogni `set` |

**Comportamento memoria:**
- Ogni `set` con `ex=90` sovrascrive il valore precedente.
- Se il flusso di punti si interrompe (client chiuso, crash, fine turno senza nuovi messaggi), la chiave decade automaticamente dopo 90 secondi.
- **Non esiste accumulo storico in Redis**: solo l'ultimo stato GPS per utente.

---

### 4.5 DATABASE — PostgreSQL 15-alpine

**Volume Docker:** `postgres_data`  
**Driver:** `psycopg-binary==3.3.4`  
**Schema principale (`migrations/versions/`):**

| Tabella | Modulo | Descrizione |
|---|---|---|
| `users` | `auth/models.py` | Utenti (`Flask-Security-Too`) |
| `roles` | `auth/models.py` | Ruoli (`user`, `admin`) |
| `groups` | `group/forms.py` / `models.py` | Gruppi con `code`, `security_token` |
| `group_memberships` | `group/models.py` | Associazione utente-gruppo con `role` (`owner` / `admin` / `member`) |
| `rider_shifts` | `gps_worker/` | Metadati turno GPS (da `session_end`) |
| `fall_events` | `gps_worker/` | Eventi caduta confermati (`is_confirmed_fall`) |

---

## 5. FLUSSO DATI COMPLETO (END-TO-END)

```
1. CLIENT MOBILE / WEB
   └─► Invia `TelemetryPoint` (JSON) → `POST https://localhost/stream`

2. NGINX (443 → 8000 /stream)
   └─► Passa a FASTAPI (`fastapi_app/main.py`)

3. FASTAPI
   └─► Serializza `point.model_dump()` → `{"type":"point", ...}`
   └─► `RabbitMQPublisher.publish(...)` → Coda `telemetry_stream` (durable)

4. RABBITMQ (`rabbitmq:5672`)
   └─► Memorizza messaggio (persistente) fino al consumo

5. GPS WORKER (`gps_worker/`)
   └─► `channel.basic_consume(...)` → `on_message()`
   └─► `stream_mgr.add_point(...)` (GPX buffer)
   └─► `redis_client.set("position:42", json.dumps(...), ex=90)`
   └─► `channel.basic_ack(...)` (rimozione dalla coda)

6. REDIS (`redis:6379`)
   └─► Memorizza `position:42` (90 s TTL)

7. UTENTE WEB (`group/detail.html`)
   └─► `pollPositions()` (`setInterval`, 8000 ms)
   └─► `fetch("/groups/5/member/42/position")`
   └─► `data.available ? updateMarker(...) : hideMarker(...)`

8. FLASK (`app/group/routes.py`)
   └─► Verifica `requester` e `target` in `group_memberships` (`group_id` uguale)
   └─► `redis_client.get("position:42")` → `jsonify({"available": True, ...})`
```

---

## 6. SICUREZZA E AUTORIZZAZIONE

### 6.1 CSRF

- **Tool:** `Flask-WTF` (`csrf = CSRFProtect()`)
- **Applicazione:** Ogni form (`auth`, `group`) include `{{ csrf_token() }}`.
- **Cookie:** `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`.

### 6.2 RBAC — Gruppi

| Ruolo (`group_memberships.role`) | Permessi |
|---|---|
| `owner` | Creazione gruppo, modifica ruoli altrui, rigenerazione codice, revoca token, cancellazione gruppo (implicita) |
| `admin` | Rigenerazione codice, revoca token, gestione inviti |
| `member` | Lettura gruppo, accesso ai dati posizione dei membri (tramite endpoint autorizzato) |

**Autorizzazione posizione (`member_position`):**

```python
requester = GroupMembership.query.filter_by(user_id=current_user.id, group_id=group_id).first()
target   = GroupMembership.query.filter_by(user_id=user_id, group_id=group_id).first()
if not requester or not target:
    abort(403)
```

**Nota:** Non esiste vincolo `current_user.id == user_id`. Quindi un membro (`requester`) può interrogare la posizione di qualsiasi altro membro (`target`) purché entrambi appartengano allo stesso `group_id`.

---

## 7. TEST E QUALITÀ

| Tool / Comando | Scopo | Stato |
|---|---|---|
| `python -m py_compile` | Verifica sintassi Python dei file modificati | **PASS** (`app/`, `extensions.py`, `config.py`, `routes.py`, `fastapi_app/`, `gps_worker/`) |
| `pytest.ini` | Configurazione test (directory `tests/`) | Configurato |
| `tests/test_group.py` | Test gruppo (esistente) | Da aggiornare con endpoint `position` se richiesto |

**File testati (sintassi):**

- `app/__init__.py`
- `extensions.py`
- `config.py`
- `app/group/routes.py`
- `gps_worker/worker_consumer.py`
- `fastapi_app/main.py`

---

## 8. COMANDI OPERATIVI

### Avvio ambiente

```bash
docker-compose up -d --build
```

### Log in tempo reale

```bash
docker-compose logs -f web        # Flask / Gunicorn
docker-compose logs -f fastapi     # FastAPI
docker-compose logs -f gps_worker  # Worker RabbitMQ
docker-compose logs -f redis       # Redis
```

### Accesso URL

| Risorsa | URL / Comando |
|---|---|
| Web App | `https://localhost` |
| Login | `https://localhost/login` |
| Gruppi | `https://localhost/groups` |
| API Stream | `POST https://localhost/stream` |
| Posizione membro (JSON) | `GET https://localhost/groups/{group_id}/member/{user_id}/position` |
| Redis CLI (docker) | `docker exec -it <redis_container> redis-cli -p 6379` |

---

## 9. NOTE DI IMPLEMENTAZIONE CRITICHE

1. **`rider_id` = `user_id`**  
   Per eliminare la discrepanza tra `str` (FastAPI `TelemetryPoint`) e `int` (DB `user_id`), il campo `rider_id` nel payload deve contenere il valore numerico dell'utente come stringa (es. `"42"`). Il validator `_coerce_user_id` lo mantiene `str`, e sia il worker (`f"position:{envelope['rider_id']}"`) che la route Flask (`f"position:{user_id}"`) generano la stessa chiave Redis.

2. **TTL 90 s — Memoria**  
   Non esiste un processo di `DEL` esplicito nel worker alla chiusura della sessione. La memoria viene liberata esclusivamente dalla scadenza automatica della chiave (`ex=POSITION_TTL`). Se si desidera una pulizia immediata, aggiungere `redis_client.delete(...)` nel branch `session_end`.

3. **Poll Frontend — 8 s**  
   `pollPositions()` usa `setInterval(pollPositions, 8000)`. Ogni iterazione esegue `fetch()` sequenziale (`for...of`) per ogni `.member-position`. Su gruppi molto grandi, considerare `Promise.all()` o debounce.

4. **Dipendenze Docker (`depends_on`)**  
   - `web` dipende da `db` e `redis`.
   - `gps_worker` dipende da `rabbitmq` (condition: `service_healthy`) e `db` / `redis` (`service_started`).
   - `fastapi` dipende da `rabbitmq` (`service_healthy`).

---

*Documento generato automaticamente in base al codice sorgente (`app/`, `fastapi_app/`, `gps_worker/`, `docker-compose.yml`, `extensions.py`, `config.py`). Ogni modifica al codice richiede l'aggiornamento del paragrafo corrispondente.*
