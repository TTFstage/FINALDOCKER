# Documentazione Funzionale del Progetto Flask Testing

Il progetto è una piattaforma ibrida sviluppata in Python che affianca un'applicazione web **Flask** per l'interfaccia e la gestione utenti, a un microservizio **FastAPI** per l'ingestione asincrona dei dati di telemetria (GPS).
L'obiettivo principale è fornire un ambiente robusto e scalabile. Flask si basa su **Flask-Security-Too** per le logiche di sicurezza e **Flask-SQLAlchemy** per l'interazione con il database PostgreSQL. L'architettura è strutturata in parte secondo il pattern **Modular Blueprint** (Application Factory) e in parte a **Microservizi** supportati da code di messaggistica (**RabbitMQ**).

## 2. Architettura Funzionale
L'applicazione è suddivisa in moduli logici (Blueprint). Attualmente, le funzionalità sono raggruppate in due macro-aree:

### 2.1 Modulo Core (Pubblico)
Gestisce le funzionalità accessibili a tutti gli utenti, inclusi quelli non autenticati.
- **Homepage (`/`)**: La pagina principale (landing page) del sito. Se l'utente è autenticato, il contesto della pagina lo riconosce (tramite `current_user`), permettendo di mostrare informazioni personalizzate o link specifici (es. link all'area privata o al logout).

### 2.2 Modulo Auth (Sicurezza e Area Personale)
Gestisce tutto il ciclo di vita dell'utente, la sicurezza e le operazioni sensibili.
- **Registrazione e Autenticazione**: Grazie all'integrazione di Flask-Security-Too, il sistema offre nativamente endpoint per il login, la registrazione e il logout. È possibile autenticarsi tramite email o username.
- **Area Privata (`/me`)**: Una rotta protetta accessibile solo agli utenti loggati (mediante il decoratore `@auth_required()`). Mostra le informazioni personali dell'utente, tra cui l'username, l'indirizzo email e l'eventuale numero di telefono.
- **Eliminazione Account (`/delete_account`)**: Funzionalità che permette all'utente di cancellare definitivamente il proprio profilo dal database. Al completamento, la sessione viene terminata (logout) e i dati vengono rimossi in modo sicuro.

### 2.3 Modulo Gruppi (RBAC)
Gestisce la creazione, l'iscrizione e l'amministrazione di gruppi privati di utenti, implementando permessi granulari (Role-Based Access Control).
- **Creazione e Accesso**: L'utente può creare nuovi gruppi, ottenendo automaticamente un codice alfanumerico univoco e un link d'invito sicuro basato su token crittografici. È possibile unirsi inserendo il codice o visitando il link.
- **Ruoli (Owner, Admin, Member)**: Sistema gerarchico interno ai gruppi. L'`owner` può promuovere/degradare membri in `admin`. Entrambi (`owner` e `admin`) possono revocare i vecchi link o rigenerare i codici di accesso per tutelare il gruppo da accessi indesiderati. I `member` hanno privilegi di sola visualizzazione dei link attivi.

### 2.4 Modulo Telemetria e Asincronia (FastAPI + RabbitMQ + Worker)
Gestisce la ricezione, l'elaborazione e il salvataggio dei flussi di dati ad alta frequenza (come la geolocalizzazione) inviati dai dispositivi.
- **Microservizio FastAPI**: Ascolta su socket e/o API REST per ingerire i dati in tempo reale a latenza bassissima, disaccoppiando questo carico dall'app Flask.
- **Coda RabbitMQ**: I dati crudi ricevuti da FastAPI vengono pubblicati in una message queue (RabbitMQ), garantendo che nessun dato vada perso in caso di picchi di carico e liberando immediatamente le connessioni web.
- **GPS Worker**: Un consumer asincrono, indipendente, in puro Python, che preleva i messaggi dalla coda, riduce i punti e le coordinate (ad es. usando l'algoritmo di Ramer-Douglas-Peucker) per ottimizzare lo storage, crea e salva su volume i file `.gpx`, e persiste i metadati dei tracciati in PostgreSQL.

## 3. Gestione dei Dati (Modelli)
Il livello dati si appoggia a un database relazionale (PostgreSQL) ed è strutturato intorno agli utenti e ai loro ruoli.

- **Entità User**: Rappresenta l'utente dell'applicativo. Memorizza in modo sicuro:
  - `username` (univoco)
  - `email` (univoco)
  - `phone_number` (opzionale, validato per inserire valore nullo se lasciato vuoto)
  - `password` (memorizzata sotto forma di hash crittografico bcrypt)
  - `active` (stato dell'utente, es. attivo/disabilitato)
- **Entità Role**: Definisce i permessi o le qualifiche (es. admin, user standard) che possono essere assegnati.
- **Associazione Utenti-Ruoli**: Una tabella di join (`roles_users`) che consente l'assegnazione di ruoli multipli a ciascun utente (relazione molti-a-molti).
- **Entità Group**: Rappresenta un gruppo isolato, dotato di un nome, una descrizione, un `code` univoco formattato per il rapido accesso, e un `security_token` url-safe a 256 bit per i link di invito.
- **Associazione Utenti-Gruppi (`GroupMembership`)**: Tabella di join avanzata che, oltre a creare la relazione tra User e Group, memorizza il ruolo (owner, admin, member) di quel particolare utente in quello specifico gruppo, supportando quindi il RBAC granulare a livello di singolo gruppo.

## 4. Requisiti di Sicurezza
Il sistema è progettato per rispettare alti standard di sicurezza web:
- **Hashing delle Password**: Utilizzo dello standard `bcrypt`. Le password in chiaro non transitano né risiedono mai nei file di log o nel database.
- **Protezione CSRF (Cross-Site Request Forgery)**: Tutte le form (incluse login, registrazione e azioni critiche come la cancellazione dell'account) richiedono un token CSRF valido, invalidando tentativi di esecuzione forzata da siti terzi.
- **Hardening della Sessione (Cookie)**: I cookie di sessione sono configurati come `HttpOnly` per prevenire attacchi XSS (Cross-Site Scripting) e con flag `SameSite=Lax` per irrobustire ulteriormente la protezione CSRF.

## 5. Manutenibilità e Database
- **Gestione delle Migrazioni**: Qualsiasi modifica strutturale ai dati (es. aggiunta di un nuovo campo utente) viene tracciata e applicata tramite migrazioni controllate (`Flask-Migrate`). Questo permette al team di sviluppo di allineare lo schema del database in modo incrementale e sicuro senza perdita di dati.

## 6. Infrastruttura e Deployment
Il progetto è containerizzato per garantire isolamento e parità tra ambienti (sviluppo e produzione).
- **Docker Compose**: Orchestratore che definisce e gestisce contemporaneamente il ciclo di vita di tutti i container del progetto. Facilita l'estensione futura del progetto per supportare worker asincroni, cache, ecc.
- **Nginx (Reverse Proxy)**: Gestisce il traffico HTTP in ingresso sulla porta 80 e lo instrada in modo sicuro ai vari servizi interni (Flask per le pagine web, FastAPI per la telemetria/api).
- **Gunicorn (App Server WSGI)**: Server WSGI per l'applicazione Flask in ambiente Linux, offrendo performance ottimali tramite worker paralleli.
- **FastAPI / Uvicorn (App Server ASGI)**: Server asincrono ad alte prestazioni dedicato all'ingestione di stream dati.
- **RabbitMQ**: Message broker utilizzato per la gestione delle code asincrone, permettendo la scalabilità dell'elaborazione telemetrica.
- **GPS Worker**: Processo background dedicato al consumo delle code di RabbitMQ e all'interazione intensiva con filesystem (scrittura file GPX) e database.
- **PostgreSQL Containerizzato**: Il database relazionale risiede nel suo container, con volume di archiviazione dedicato.
- **Entrypoint Script**: Il container web avvia uno script dedicato che assicura l'accessibilità al database prima di avviare il processo Gunicorn, gestendo anche le migrazioni del DB.
