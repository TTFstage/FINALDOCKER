# Piano di Riorganizzazione Frontend & Backend

## Contesto e Obiettivo

Il sito attuale ha una navbar piatta e disorganizzata:
`Home | Profilo | SOS | Gruppi | Mappa | Analytics | Logout`

L'obiettivo è riorganizzare in una struttura gerarchica e pulita:
`Home | Map | Analytics | Other`

Dove **Other** raccoglie le sezioni secondarie (Profile, Groups e la nuova **SOS Contacts**) e **Home** diventa il pannello operativo principale (solo sessione GPS + pulsante di emergenza).

---

## Analisi dello Stato Attuale

### Blueprint Flask registrati in `app/__init__.py`
| Blueprint | Prefisso URL | Nome interno |
|---|---|---|
| `core_bp` | `/` | `core` |
| `auth_bp` | `/auth` | `auth` |
| `group_bp` | `/groups` | `group` |
| `telemetry_bp` | `/telemetry` | `telemetry` |
| `map_pages_bp` | `/map` | `map_pages` |
| `map_api_bp` | *(vario)* | `map_api` |
| `analytics_bp` | `/analytics` | `analytics` |

### Template attuali e loro contenuto
| Template | Contenuto attuale | Destinazione |
|---|---|---|
| `templates/base.html` | Navbar principale, flash messages | **Modificare** navbar |
| `templates/core/index.html` | Btn start/stop sessione + link a profilo/SOS/gruppi | **Modificare**: solo sessione GPS + crash-alert overlay |
| `templates/auth/private_page.html` | Dati profilo + lista SOS contacts + elimina account | **Modificare**: rimuovere SOS, aggiungere logout |
| `templates/auth/sos_contacts_list.html` | Lista contatti SOS separata | Back-link aggiornato → `other.index` |
| `templates/auth/sos_contact_form.html` | Form add/edit contatto SOS | Back-link aggiornato → `other.index` |
| `templates/group/index.html` | Lista gruppi + link crea/entra + link Home | **Modificare**: rimuovere link Home ridondante |
| `templates/group/create.html` | Form crea gruppo | Invariato |
| `templates/group/detail.html` | Dettaglio gruppo + membri + gestione | Invariato |
| `templates/group/join.html` | Form codice di join | Invariato |
| `templates/group/join_invite.html` | Accetta invito via token | Invariato |
| `templates/map/map.html` | Mappa Leaflet + navigatore | **Invariato** |
| `templates/analytics/index.html` | Selezione GPX + mappa + statistiche | **Invariato** |

---

## Struttura Finale Attesa

```
Navbar: Home | Map | Analytics | Other
│
├── Home (/)
│   ├── Tasto "Inizia Sessione GPS"
│   ├── Tasto "Ferma Sessione GPS"
│   ├── Stato corrente sessione (#status)
│   └── Overlay crash-alert SOS (gestito da main.js / FallDetector)
│   [NON contiene lista contatti SOS, né link a profilo/gruppi]
│
├── Map (/map/)
│   └── Identica a ora (Leaflet, navigatore, overlay)
│
├── Analytics (/analytics/)
│   └── Identica a ora (select GPX, mappa, stats)
│
└── Other (/other/)   ← pagina hub con 3 link
    ├── Link → Profile (/auth/me)
    ├── Link → Groups (/groups/)
    └── Link → SOS Contacts (/auth/sos/contacts)

    ├── Profile (/auth/me)
    │   ├── Dati utente (username, email, telefono)
    │   ├── Tasto Logout (form POST → /security/logout)
    │   └── Tasto Elimina Account (form POST → /auth/delete_account)
    │
    ├── Groups (/groups/)
    │   ├── Lista gruppi di cui faccio parte (con ruolo)
    │   ├── Tasto "+ Crea Gruppo" → /groups/create
    │   ├── Tasto "Entra con Codice" → /groups/join
    │   └── Ogni gruppo → /groups/<id> (dettaglio, membri, gestione inviti)
    │
    └── SOS Contacts (/auth/sos/contacts)
        ├── Lista contatti SOS (nome, telefono, relazione, priorità)
        ├── Tasto "+ Aggiungi contatto" → /auth/sos/contacts/add
        ├── Per ogni contatto: Modifica → /auth/sos/contacts/<id>/edit
        └── Per ogni contatto: Elimina → POST /auth/sos/contacts/<id>/delete
```

> **Nota importante**: I contatti SOS diventano una sezione autonoma sotto **Other** (non più in Home, non in Profile).
> Il Logout viene spostato dalla navbar alla pagina Profile.

---

## Piano Dettagliato delle Modifiche

---

### FASE 1 — Backend Flask: Nuovo Blueprint `other`

**Obiettivo**: Creare un blueprint leggero che serva la pagina hub `/other/`.

#### Step 1.1 — Creare la directory `app/other/` con i relativi file

**`app/other/__init__.py`**
```python
from flask import Blueprint

other_bp = Blueprint('other', __name__)

from app.other import routes  # noqa: E402, F401
```

**`app/other/routes.py`**
```python
from flask import render_template
from flask_security import auth_required

from app.other import other_bp


@other_bp.route('/')
@auth_required()
def index():
    """Pagina hub con i link a Profile e Groups."""
    return render_template('other/index.html')
```

#### Step 1.2 — Registrare il blueprint in `app/__init__.py`

Nel file `app/__init__.py`, aggiungere le righe seguenti **dopo** la riga `from app.analytics import analytics_bp` e **prima** del `return app`:

```python
# Other hub
from app.other import other_bp
app.register_blueprint(other_bp, url_prefix='/other')
```

---

### FASE 2 — Note sulle Route SOS (nessuna modifica backend)

Le route SOS rimangono nel blueprint `auth` (URL `/auth/sos/...`).
**Non si spostano le route Python** — viene aggiornata solo la navigazione nei template.

> Questo significa **nessuna modifica strutturale a `app/auth/routes.py`** per le route SOS. Le URL esistenti restano valide e accessibili.

---

### FASE 3 — Backend: Modificare `app/auth/routes.py` (funzione `me`)

La route `auth_bp.me` attualmente recupera i contatti SOS per passarli al template Profile. Poiché Profile non mostra più i contatti SOS, questa query diventa inutile e va rimossa.

**File**: `app/auth/routes.py`, funzione `me()` (righe 11-28)

```python
# PRIMA:
@auth_bp.get("/me")
@auth_required()
def me():
    sos_contacts = (
        SOSContact.query.filter_by(user_id=current_user.id)
        .order_by(SOSContact.priority.desc(), SOSContact.created_at.asc())
        .all()
    )
    return render_template(
        "auth/private_page.html",
        username=current_user.username,
        phone_number=current_user.phone_number,
        email=current_user.email,
        sos_contacts=sos_contacts
    )

# DOPO:
@auth_bp.get("/me")
@auth_required()
def me():
    """Pagina del profilo utente: dati, logout e delete account."""
    return render_template(
        "auth/private_page.html",
        username=current_user.username,
        phone_number=current_user.phone_number,
        email=current_user.email,
    )
```

> Se l'import `SOSContact` in cima al file diventa inutilizzato dopo questa modifica, rimuoverlo dall'import della funzione `me`. Verificare che sia ancora usato altrove nel file (nelle route `/sos/contacts/...`) — se sì, lasciare l'import.

---

### FASE 4 — Backend: `app/core/routes.py` — Nessuna modifica necessaria

Poiché i contatti SOS non vengono più mostrati in Home, la route `core_bp.index` **non ha bisogno di passare `sos_contacts` al template**. Il file rimane invariato rispetto allo stato attuale.

> **Nessuna azione richiesta** in questa fase. `app/core/routes.py` è nella lista dei file **invariati**.

---

### FASE 5 — Template: `base.html` — Nuova Navbar

**File**: `app/templates/base.html`

Riscrivere completamente il file con i seguenti cambiamenti:
1. Aggiungere `<meta name="viewport">` per responsività.
2. Aggiungere `<link rel="stylesheet">` che carica `style.css` (attualmente **mancante** — il CSS non veniva applicato su nessuna pagina).
3. Aggiungere `{% block head %}{% endblock %}` per permettere CSS extra per pagina (usato da analytics e map).
4. Sostituire il `<nav>` con la nuova struttura (4 voci: Home, Map, Analytics, Other).
5. Rimuovere Logout dalla navbar.
6. Aggiungere `{% block scripts %}{% endblock %}` in fondo al body (usato da analytics e map per JS extra).

**Contenuto completo del nuovo `base.html`**:

```html
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Web App{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    <nav>
        <a href="{{ url_for('core.index') }}">Home</a>
        {% if current_user and current_user.is_authenticated %}
            | <a href="{{ url_for('map_pages.home') }}">Map</a>
            | <a href="{{ url_for('analytics.index') }}">Analytics</a>
            | <a href="{{ url_for('other.index') }}">Other</a>
        {% else %}
            | <a href="{{ url_for('security.login') }}">Login</a>
            | <a href="{{ url_for('security.register') }}">Register</a>
        {% endif %}
    </nav>
    <hr>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <p style="color: {% if category == 'error' %}red{% elif category == 'success' %}green{% else %}blue{% endif %};">
                    [{{ category }}] {{ message }}
                </p>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}

    {% block scripts %}{% endblock %}
</body>
</html>
```

**Cosa sparisce dalla navbar**:
- Link diretto a "Profilo"
- Link diretto a "SOS"
- Link diretto a "Gruppi"
- Form Logout inline nella navbar

---

### FASE 6 — Template: `core/index.html` — Nuova Home

**File**: `app/templates/core/index.html`

Riscrivere il contenuto del `{% block content %}` mantenendo tutti gli script esistenti e aggiungendo la sezione SOS.

**Contenuto completo del nuovo `core/index.html`**:

```html
{% extends "base.html" %}
{% block title %}Home{% endblock %}

{% block content %}
<h1>Benvenuto</h1>

{% if current_user and current_user.is_authenticated %}
    <p>Ciao, {{ current_user.username }}!</p>

    <!-- SEZIONE SESSIONE GPS -->
    <section id="session-section">
        <button id="btn-start" class="btn" onclick="startTracking();">Inizia Tracciamento GPS</button>
        <button id="btn-stop" class="btn" onclick="stopTracking();" style="display:none;">Ferma Tracciamento GPS</button>
        <p id="status">Stato: Tracciamento fermato.</p>
    </section>

{% else %}
    <p>
        <a href="{{ url_for('security.login') }}">Accedi</a> |
        <a href="{{ url_for('security.register') }}">Registrati</a>
    </p>
{% endif %}

<!-- OVERLAY CRASH ALERT / SOS (gestito da main.js) -->
<div id="crash-alert">
    <h1>⚠️ CADUTA RILEVATA</h1>
    <p>Invio SOS tra:</p>
    <div id="timer-display">10</div>
    <button class="btn-cancel" onclick="cancelSOS()">ANNULLA</button>
</div>

<script>window.RIDER_ID = {{ current_user.id if current_user.is_authenticated else 'null' }};</script>
<script src="{{ url_for('static', filename='js/SignalProcessor.js') }}"></script>
<script src="{{ url_for('static', filename='js/HeadingEstimator.js') }}"></script>
<script src="{{ url_for('static', filename='js/FallDetector.js') }}"></script>
<script src="{{ url_for('static', filename='js/main.js') }}"></script>
{% endblock %}
```

**Cosa cambia rispetto all'attuale**:
- Rimossi i link rapidi a Profilo, SOS, Gruppi
- **Rimossa** la sezione SOS con lista contatti inline (ora è una sezione separata in Other)
- Aggiunto overlay crash-alert (già presente in `style.css` ma mancava nel template)
- La Home è ora focalizzata esclusivamente sulla sessione GPS e sul rilevamento cadute

---

### FASE 7 — Template: `auth/private_page.html` — Nuova Pagina Profile

**File**: `app/templates/auth/private_page.html`

**Contenuto completo del nuovo `private_page.html`**:

```html
{% extends "base.html" %}
{% block title %}Profilo{% endblock %}

{% block content %}
<h1>Profilo</h1>
<p><strong>Username:</strong> {{ username }}</p>
<p><strong>Email:</strong> {{ email }}</p>
<p><strong>Telefono:</strong> {{ phone_number if phone_number else 'Non impostato' }}</p>

<hr>

<!-- LOGOUT -->
<h2>Sessione</h2>
<form method="POST" action="{{ url_for('security.logout') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <button type="submit">Logout</button>
</form>

<hr>

<!-- ELIMINA ACCOUNT -->
<h2>Zona Pericolosa</h2>
<form method="POST" action="{{ url_for('auth.delete_account') }}" onsubmit="return confirm('Sei sicuro di voler eliminare il tuo account? Questa azione è irreversibile.');">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <button type="submit">Elimina Account</button>
</form>
{% endblock %}
```

**Cosa cambia rispetto all'attuale**:
- Rimossa intera sezione Contatti SOS (righe 12-32 del file attuale)
- Aggiunto form Logout (spostato dalla navbar)
- Rimosso il link `← Torna alla home` (la navbar gestisce la navigazione)

---

### FASE 8 — Template: `other/index.html` — Pagina Hub "Other" (NUOVO)

**File da creare**: `app/templates/other/index.html`

Questa pagina hub espone **tre** sezioni: Profile, Groups e la nuova **SOS Contacts**.

```html
{% extends "base.html" %}
{% block title %}Other{% endblock %}

{% block content %}
<h1>Other</h1>
<p>Seleziona una sezione:</p>
<ul>
    <li>
        <a href="{{ url_for('auth.me') }}">Profilo</a>
        — Dati account, logout, elimina account
    </li>
    <li>
        <a href="{{ url_for('group.index') }}">Gruppi</a>
        — I tuoi gruppi, crea o unisciti a un gruppo
    </li>
    <li>
        <a href="{{ url_for('auth.list_sos_contacts') }}">Contatti SOS</a>
        — Gestisci i tuoi contatti di emergenza (max 5)
    </li>
</ul>
{% endblock %}
```

---

### FASE 9 — Template: `group/index.html` — Aggiustamento

**File**: `app/templates/group/index.html`

**Cambiamento**: rimuovere il link `| Home` dalla barra azioni in cima (riga 10 del file attuale), poiché la navbar gestisce già la navigazione.

```html
<!-- PRIMA (riga 7-11): -->
<p>
    <a href="{{ url_for('group.create') }}">+ Crea gruppo</a> |
    <a href="{{ url_for('group.join') }}">Entra con codice</a> |
    <a href="{{ url_for('core.index') }}">Home</a>
</p>

<!-- DOPO: -->
<p>
    <a href="{{ url_for('group.create') }}">+ Crea gruppo</a> |
    <a href="{{ url_for('group.join') }}">Entra con codice</a>
</p>
```

---

### FASE 10 — Template: Aggiornamento Back-link nei template SOS

#### `app/templates/auth/sos_contacts_list.html` (riga 7)

La pagina lista SOS è ora raggiungibile da Other. Il link di ritorno da "← Profilo" va aggiornato a "← Other".

```html
<!-- PRIMA (riga 7): -->
<p><a href="{{ url_for('auth.add_sos_contact') }}">+ Aggiungi nuovo contatto</a> | <a href="{{ url_for('auth.me') }}">← Profilo</a></p>

<!-- DOPO: -->
<p><a href="{{ url_for('auth.add_sos_contact') }}">+ Aggiungi nuovo contatto</a> | <a href="{{ url_for('other.index') }}">← Other</a></p>
```

#### `app/templates/auth/sos_contact_form.html` (riga 7)

Il form di aggiunta/modifica ha un link `← Annulla`. Deve portare alla lista SOS (comportamento già corretto — `auth.list_sos_contacts`), quindi **nessuna modifica necessaria qui**.

```html
<!-- GIÀ CORRETTO (riga 7): -->
<p><a href="{{ url_for('auth.list_sos_contacts') }}">← Annulla</a></p>
<!-- Questo link è già corretto: torna alla lista SOS, che è la pagina padre del form -->
```

> **Riassunto**: Solo `sos_contacts_list.html` ha bisogno di un aggiornamento al back-link. Il form `sos_contact_form.html` rimane invariato.

---

## Riepilogo File da Modificare

### File **Nuovi** da creare
| File | Motivo |
|---|---|
| `app/other/__init__.py` | Definisce il Blueprint `other` |
| `app/other/routes.py` | Route `/other/` per la pagina hub |
| `app/templates/other/index.html` | Template della pagina hub Other |

### File **Esistenti** da modificare
| File | Tipo di modifica | Fase |
|---|---|---|
| `app/__init__.py` | Registrare `other_bp` con prefisso `/other` | Fase 1.2 |
| `app/auth/routes.py` | Rimuovere query SOS da `me()` | Fase 3 |
| `app/templates/base.html` | Nuova navbar (4 voci), aggiungere `{% block head %}`, `{% block scripts %}`, link al CSS | Fase 5 |
| `app/templates/core/index.html` | Rimuovere link rapidi e sezione SOS, aggiungere crash-alert overlay, mantenere sessione GPS | Fase 6 |
| `app/templates/auth/private_page.html` | Rimuovere SOS, aggiungere Logout, rimuovere link torna home | Fase 7 |
| `app/templates/group/index.html` | Rimuovere link `| Home` dalla barra azioni | Fase 9 |
| `app/templates/auth/sos_contacts_list.html` | Back-link → `other.index` | Fase 10 |

### File **Invariati** (nessuna modifica necessaria)
| File | Motivo |
|---|---|
| `app/core/routes.py` | Non serve più passare `sos_contacts` alla Home |
| `app/map/routes.py` | Le route mappa non cambiano |
| `app/analytics/routes.py` | Le route analytics non cambiano |
| `app/group/routes.py` | Le route gruppi non cambiano |
| `app/auth/forms.py` | I form SOS non cambiano |
| `app/auth/models.py` | I modelli non cambiano |
| `app/templates/map/map.html` | La pagina mappa rimane invariata |
| `app/templates/analytics/index.html` | La pagina analytics rimane invariata |
| `app/templates/group/create.html` | Back-link già corretto (`group.index`) |
| `app/templates/group/detail.html` | Back-link già corretto (`group.index`) |
| `app/templates/group/join.html` | Back-link già corretto (`group.index`) |
| `app/templates/group/join_invite.html` | Funzionamento invariato |
| `app/templates/auth/sos_contact_form.html` | Back-link a `auth.list_sos_contacts` già corretto |
| `app/static/js/main.js` | La logica SOS/GPS non cambia |
| `app/static/js/FallDetector.js` | Invariato |
| `app/static/js/SignalProcessor.js` | Invariato |
| `app/static/js/HeadingEstimator.js` | Invariato |
| `app/static/style.css` | Il CSS è già corretto; viene solo collegato correttamente via `base.html` |

---

## Ordine di Esecuzione Raccomandato

Seguire questo ordine riduce al minimo i rischi di errori intermedi.

```
1.  [BACKEND]   Creare app/other/__init__.py
2.  [BACKEND]   Creare app/other/routes.py
3.  [BACKEND]   Modificare app/__init__.py → registrare other_bp
4.  [FRONTEND]  Creare app/templates/other/index.html (con 3 link: Profile, Groups, SOS Contacts)
5.  [BACKEND]   Modificare app/auth/routes.py → rimuovere SOS da me()
6.  [FRONTEND]  Modificare app/templates/base.html → nuova navbar
7.  [FRONTEND]  Modificare app/templates/core/index.html → solo sessione GPS + crash-alert
8.  [FRONTEND]  Modificare app/templates/auth/private_page.html → Profile pulita + Logout
9.  [FRONTEND]  Modificare app/templates/group/index.html → rimuovere link Home
10. [FRONTEND]  Modificare app/templates/auth/sos_contacts_list.html → back-link → other.index
11. [VERIFICA]  Test completo del flusso (vedi tabella sotto)
```

---

## Piano di Verifica

### Test manuali da eseguire dopo le modifiche

| # | Scenario | Cosa verificare | Esito atteso |
|---|---|---|---|
| 1 | Utente non autenticato → Home | Navbar mostra `Home \| Login \| Register` | ✅ |
| 2 | Utente non autenticato → `/other/` | Redirect a Login | ✅ |
| 3 | Utente non autenticato → `/map/` | Redirect a Login | ✅ |
| 4 | Login → Home | Navbar `Home \| Map \| Analytics \| Other` | ✅ |
| 5 | Home → sezione sessione GPS | Bottone Start/Stop visibili, stato aggiornato | ✅ |
| 6 | Home → **nessuna lista SOS** | La Home non mostra contatti SOS, solo sessione GPS | ✅ |
| 7 | Home → FallDetector attiva SOS | Overlay crash-alert appare con countdown | ✅ |
| 8 | Overlay SOS → click "ANNULLA" | Overlay scompare, SOS non inviato | ✅ |
| 9 | Navbar → "Map" | Pagina mappa aperta, identica a prima | ✅ |
| 10 | Navbar → "Analytics" | Pagina analytics aperta, identica a prima | ✅ |
| 11 | Navbar → "Other" | Pagina hub con 3 link: Profile, Groups, Contatti SOS | ✅ |
| 12 | Other → click "Profilo" | Pagina profilo con dati, Logout, Elimina Account (NO lista SOS) | ✅ |
| 13 | Profile → click "Logout" | Utente disconnesso, redirect a Login | ✅ |
| 14 | Profile → click "Elimina Account" | Dialog di conferma appare | ✅ |
| 15 | Profile → conferma "Elimina Account" | Account eliminato, redirect a Home | ✅ |
| 16 | Other → click "Gruppi" | Lista gruppi, tasto Crea, tasto Entra con codice | ✅ |
| 17 | Groups → "Crea gruppo" | Form creazione, after submit → dettaglio gruppo | ✅ |
| 18 | Groups → "Entra con codice" | Form join, back-link porta a `group.index` | ✅ |
| 19 | Groups → click su un gruppo | Pagina dettaglio con membri, gestione ruoli, link invito | ✅ |
| 20 | Link invito gruppo (`/groups/join/<token>`) | Pagina accetta invito → pulsante unisciti | ✅ |
| 21 | Other → click "Contatti SOS" | Pagina lista SOS (`/auth/sos/contacts`) | ✅ |
| 22 | SOS Contacts → lista vuota | Messaggio "Nessun contatto SOS" + link "+ Aggiungi" | ✅ |
| 23 | SOS Contacts → click "+ Aggiungi" | Form SOS si apre (`/auth/sos/contacts/add`) | ✅ |
| 24 | Form SOS → submit valido | Contatto salvato, redirect a lista SOS | ✅ |
| 25 | Form SOS → click "← Annulla" | Redirect a lista SOS (back-link invariato e corretto) | ✅ |
| 26 | SOS Contacts → click "← Other" | Redirect a `/other/` | ✅ |
| 27 | Nessun link rotto | Tutti i `url_for()` nei template risolvono route esistenti | ✅ |

---

## Note Tecniche Importanti

### 1. CSS mancante in `base.html`
Il file `base.html` attuale **non carica `style.css`**. Tutti gli stili definiti (pulsanti, overlay SOS, form) non venivano applicati su nessuna pagina (eccetto forse per qualche pagina che lo includeva manualmente). La Fase 5 risolve questo con l'aggiunta del `<link rel="stylesheet">`.

### 2. Blocchi `{% block head %}` e `{% block scripts %}` mancanti
I template `analytics/index.html` e `map/map.html` usano rispettivamente `{% block head %}` e `{% block scripts %}`, ma questi blocchi non sono definiti in `base.html`. Ciò significa che tutto il CSS/JS specifico di quelle pagine (Leaflet, leaflet-gpx) viene ignorato. La Fase 5 risolve questo.

### 3. Logout form — CSRF token obbligatorio
Flask-Security richiede che il logout avvenga via `POST` con token CSRF. Il form Logout spostato in Profile **deve** includere `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>` — già incluso nel template proposto.

### 4. Route `/auth/sos/contacts` — ora entry point principale
La pagina lista SOS (`/auth/sos/contacts`) era precedentemente un endpoint secondario raggiungibile solo da Profilo. Ora è una **sezione di primo livello sotto Other**, linkata direttamente da `other/index.html`. Le route esistenti non cambiano — si aggiorna solo il back-link in `sos_contacts_list.html` da `← Profilo` a `← Other`.

### 5. `other_bp` — sicurezza `@auth_required()`
La pagina hub `/other/` usa `@auth_required()`, quindi un utente non autenticato che prova ad accedere direttamente a `/other/` viene reindirizzato al login da Flask-Security senza modifiche aggiuntive.

### 6. Import circolare in `app/other/__init__.py`
L'import `from app.other import routes` viene fatto **dopo** la creazione del Blueprint per evitare import circolari, seguendo lo stesso pattern già usato in `app/group/__init__.py`.
