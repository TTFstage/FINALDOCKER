# Flask Security Testing

> 📄 **Documentazione tecnica completa e professionale:** `DOCUMENTAZIONE_TECNICA.md` — include stack, architettura, flusso dati, sicurezza, Redis TTL e comandi operativi.

Questo è un progetto completo che dimostra l'implementazione di un'applicazione web sicura e di una pipeline di ingestione dati ad alte prestazioni (microservizi).
Il cuore dell'applicazione web utilizza **Flask** e `Flask-Security-Too` per gestire in modo robusto la registrazione, il login e la gestione degli utenti (incluso un sistema RBAC per gruppi), appoggiandosi a un database PostgreSQL tramite `Flask-SQLAlchemy`. L'applicazione adotta una **Modular Blueprint Architecture** per garantire manutenibilità.
In parallelo, il progetto integra **FastAPI**, **RabbitMQ** e un **GPS Worker** per l'ingestione asincrona e l'elaborazione di dati telemetrici (es. tracciati GPS), dimostrando un'architettura ibrida e scalabile.

---

## 🏛️ Architettura del Progetto (Ibrida: Monolite Modulare + Microservizi)

Il progetto affianca a un'applicazione Flask basata sul pattern **Application Factory** e **Blueprint**, una pipeline a microservizi per i dati ad alta frequenza. Questo approccio ibrido permette di gestire l'interfaccia utente e l'autenticazione in modo coeso e scalare le operazioni intensive (come l'ingestione di dati GPS) su processi separati.

### Struttura delle Directory

```text
FlaskTesting/
├── .env                  # Variabili d'ambiente (non versionato in git)
├── docker-compose.yml    # File di orchestrazione dei container (Web, FastAPI, Worker, RabbitMQ, Redis, Nginx, DB)
├── Dockerfile            # Configurazione per la build del container Flask
├── entrypoint.sh         # Script di avvio per eseguire migrazioni e Gunicorn
├── nginx/                # Configurazione del reverse proxy Nginx
├── fastapi_app/          # Microservizio FastAPI per l'ingestione della telemetria
├── gps_worker/           # Worker background per il processing asincrono dei dati GPS
├── wsgi.py               # Entry point per l'esecuzione del server Flask
├── config.py             # File di configurazione dell'app (Classi Config)
├── extensions.py         # Istanziazione globale delle estensioni (DB, Security, Migrate)
├── app/                  # Package principale dell'applicazione Flask
│   ├── __init__.py       # Factory Function: assembla l'app, le config e i blueprint
│   ├── core/             # Blueprint: Modulo per le funzionalità pubbliche e generiche
│   ├── auth/             # Blueprint: Modulo di dominio (Sicurezza e Account)
│   ├── group/            # Blueprint: Modulo per la gestione dei gruppi, permessi (RBAC) e posizione GPS in tempo reale
│   └── templates/        # Template Jinja2 organizzati per modulo
├── migrations/           # Autogenerato da Flask-Migrate (storico schema DB)
├── requirements.txt      # Dipendenze di produzione (Gunicorn, Flask, ecc.)
├── requirements-dev.txt  # Dipendenze di sviluppo (pytest, ruff, ecc.)
└── README.md             # Questa documentazione
```

---

## 🛠️ Guida per lo Sviluppatore: Come aggiornare e scalare il progetto

Quando devi aggiungere nuove funzionalità, la regola d'oro è **separazione delle responsabilità**. Non mettere tutto in `routes.py` o `models.py`. Pensa per "moduli" (Blueprint).

Ecco una guida esaustiva su dove inserire ogni tipo di file:

### 1. Aggiungere una nuova funzionalità indipendente (Nuovo Blueprint)

Se devi aggiungere un'intera nuova sezione (es. un blog, un e-commerce, un pannello admin), crea una nuova cartella sotto `app/`:

1. Crea la cartella: `app/blog/`
2. Aggiungi `app/blog/routes.py`:

    ```python
    from flask import Blueprint, render_template
    blog_bp = Blueprint('blog', __name__)

    @blog_bp.route('/blog')
    def index():
        return "Il mio blog!"
    ```

3. Registra il Blueprint in `app/__init__.py`:
    ```python
    from app.blog.routes import blog_bp
    app.register_blueprint(blog_bp)
    ```

### 2. Aggiungere nuove Tabelle al Database (Modelli)

I modelli devono stare nel modulo a cui appartengono logicamente.

- Se aggiungi tabelle legate agli utenti (es. "Log Accessi"), mettile in `app/auth/models.py`.
- Se hai creato il modulo "Blog", crea `app/blog/models.py` e definisci lì i modelli (es. `Post`, `Comment`).
  **Ricorda:** Qualsiasi file che contiene modelli deve importare l'istanza `db` da `extensions.py` (e non da `__init__.py`). Dopo aver modificato o aggiunto modelli, ricorda sempre di eseguire le migrazioni: `flask db migrate -m "messaggio"` e poi `flask db upgrade`.

### 3. Aggiungere Pagine HTML (Templates)

I template seguono la stessa divisione dei Blueprint:

- I file HTML vanno inseriti in `app/templates/NOME_DEL_MODULO/`.
- Fai sempre iniziare il tuo nuovo file HTML estendendo il layout principale: `{% extends "base.html" %}`.
- Questo preverrà conflitti di nomi. Ad esempio, puoi avere `app/templates/auth/index.html` e `app/templates/blog/index.html` senza che si sovrascrivano.

### 4. Aggiungere file Statici (CSS, JS, Immagini)

Crea una cartella `static/` dentro `app/` (`app/static/`).
Come per i template, è best practice creare sottocartelle per modulo o per tipo (es. `app/static/css/style.css` o `app/static/blog/blog.js`).
Nei template li richiamerai con: `{{ url_for('static', filename='css/style.css') }}`.

### 5. Aggiungere nuove Estensioni (es. Flask-Mail, Celery)

Non inizializzare **mai** le estensioni dentro `app/__init__.py` o nei file delle rotte, altrimenti genererai dipendenze cicliche.

1. Istanzia l'estensione in `extensions.py` (es. `mail = Mail()`).
2. Importala e associala all'app in `app/__init__.py` dentro la funzione `create_app()` (es. `mail.init_app(app)`).
3. Importala nei vari moduli (`routes.py`) dove ti serve utilizzarla (es. `from extensions import mail`).

### 6. Modificare i Form o l'Autenticazione

Tutto ciò che riguarda l'autenticazione si trova in `app/auth/`.

- Per aggiungere campi al form di registrazione, modifica `app/auth/forms.py`.
- Per cambiare il modo in cui vengono mostrate le pagine di login nativo, modifica i file HTML dentro `app/templates/security/`. (Flask-Security-Too cercherà automaticamente in quella specifica cartella).
- Per cambiare regole globali (es. la durata delle password o il token), modifica `config.py`.

---

## 🔒 Funzionalità Principali (Security)

- **Autenticazione Sicura:** Gestita da `Flask-Security-Too`.
- **Supporto Username/Email:** Login consentito tramite email o username (case-insensitive).
- **Hashing:** Le password usano lo standard di settore `bcrypt`.
- **Protezione CSRF:** Abilitata su tutti i form (incluso login/logout) tramite il token `{{ csrf_token() }}`.
- **Hardening Cookie:** `HttpOnly` e `SameSite=Lax` per prevenire attacchi XSS e CSRF.
- **DB e Migrazioni:** Utilizzo di `psycopg3` e `Flask-Migrate`.
- **Redis:** Memoria per la posizione GPS in tempo reale (`position:{user_id}`, TTL 90s) tramite `redis_client` condiviso.

---

## 👥 Gestione Gruppi (RBAC)

Il progetto include un sistema di gestione dei gruppi con controllo degli accessi basato sui ruoli (RBAC):

- **Creazione e Accesso:** Gli utenti possono creare nuovi gruppi o unirsi a gruppi esistenti tramite un codice univoco (es. `abc-defg-hij`) o un link d'invito crittografico.
- **Ruoli e Permessi:** Ogni membro ha un ruolo assegnato (`owner`, `admin`, `member`).
    - L'`owner` ha il controllo totale, inclusa la promozione e rimozione degli `admin`.
    - Gli `admin` (e l'`owner`) possono rigenerare i codici di accesso e revocare i link d'invito per prevenire accessi indesiderati.
    - I `member` hanno privilegi di sola lettura per i link di invito attivi.
- **Sicurezza Inviti:** I link d'invito utilizzano token sicuri a 256 bit generati tramite `secrets` e possono essere invalidati istantaneamente.

---

## 📍 Posizione GPS in Tempo Reale (Gruppo)

- **Ingestione:** Il client invia `user_id` nel campo `rider_id` del payload FastAPI (`TelemetryPoint`).
- **Storage:** Il `gps_worker` scrive in Redis (`position:{user_id}`) con TTL 90s (`redis==5.2.1`).
- **Autorizzazione:** La route Flask `/groups/<group_id>/member/<user_id>/position` verifica server-side che entrambi i membri facciano parte dello stesso `group_id`.
- **Polling:** Il frontend (`group/detail.html`) interroga ogni 8s tramite `pollPositions()` e aggiorna il marker Leaflet (`updateMarker` / `hideMarker`).
- **Memoria:** La chiave è un singolo record (ultimo punto GPS), non una lista; non cresce nel tempo.

---

## 🚀 Prerequisiti, Installazione e Avvio (Docker)

L'applicazione è interamente containerizzata e richiede solo Docker per essere avviata. L'infrastruttura comprende:

- **Gunicorn** (Web Server WSGI per Flask)
- **FastAPI** (Web Server ASGI per l'ingestione telemetria)
- **RabbitMQ** (Message Broker per disaccoppiare l'elaborazione)
- **GPS Worker** (Processo background per consumare messaggi e generare GPX)
- **Nginx** (Reverse Proxy che instrada su Flask e FastAPI)
- **PostgreSQL** (Database)

### Prerequisiti

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installato e avviato sul sistema.

### Setup e Avvio Rapido

1. **Clona il repository**
2. **Configura l'ambiente (`.env`):**
   Crea un file `.env` copiando questo schema (opzionale, `docker-compose.yml` ha già dei default):
    ```env
    SECRET_KEY=la_tua_secret_key_super_sicura
    SECURITY_PASSWORD_SALT=il_tuo_salt_super_sicuro
    DB_USER=postgres
    DB_PASSWORD=latuapassword
    DB_NAME=testlogin
    ```
3. **Avvia l'ambiente con Docker Compose:**
   Nel terminale, nella cartella principale del progetto esegui:
    ```bash
    docker-compose up -d --build
    ```
4. **Verifica l'avvio:**
   L'applicazione avvierà automaticamente il database, eseguirà le migrazioni in sospeso e avvierà Nginx.
    ### 🌐 Indirizzi di Accesso
    | Servizio             | URL                                                             | Descrizione                                 |
    | -------------------- | --------------------------------------------------------------- | ------------------------------------------- |
    | **Applicazione Web** | `https://localhost`                                             | Applicazione Flask (login, gruppi, profilo) |
    | **Login**            | `https://localhost/login`                                       | Pagina di accesso                           |
    | **Registrazione**    | `https://localhost/register`                                    | Creazione nuovo account                     |
    | **Profilo**          | `https://localhost/auth/me`                                     | Area personale utente                       |
    | **Gruppi**           | `https://localhost/groups`                                      | Gestione gruppi                             |
    | **Contatti SOS**     | `https://localhost/auth/sos/contacts`                           | Lista contatti SOS                          |
    | **Aggiungi SOS**     | `https://localhost/auth/sos/contacts/add`                       | Aggiungi nuovo contatto                     |
    | **Posizione Membro** | `https://localhost/groups/{group_id}/member/{user_id}/position` | Posizione GPS in tempo reale (JSON)         |
    | **API Telemetria**   | `https://localhost/stream`                                      | Endpoint FastAPI per GPS                    |
    > ⚠️ **Nota:** L'accesso HTTP su `http://localhost` reindirizza automaticamente a HTTPS.

### Visualizzazione dei log

Per visualizzare i log in tempo reale dell'applicazione:

```bash
docker-compose logs -f web
```

### Come fermare l'applicazione

Per spegnere i container (senza perdere i dati del database), esegui nel terminale:

```bash
docker-compose down
```

Se desideri eliminare anche i volumi (incluso il database, **attenzione: perderai tutti i dati**), usa:

```bash
docker-compose down -v
```

---

## 💾 Comandi Utili per il Database (Flask-Migrate)

- `flask db migrate -m "Descrizione"`: Genera una nuova migrazione (da lanciare dopo aver modificato i modelli Python).
- `flask db upgrade`: Applica le migrazioni generate al database.
- `flask db downgrade`: Annulla l'ultima migrazione.
- `flask db current`: Visualizza la migrazione attuale.

### Come popolare il database con i dati della mappa

Per caricare i dati della mappa (fontanelle, bagni, parcheggi bici) nel database PostgreSQL a partire dai file CSV (nella cartella `data/`), esegui questo comando nel terminale mentre i container sono attivi:

```bash
docker-compose exec -e PYTHONPATH=/app web python scripts/import_map_data.py
```
