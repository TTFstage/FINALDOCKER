// ==========================================
// VARIABILI DI STATO E CONFIGURAZIONE
// ==========================================
let watchId = null;            // ID del sensore di geolocalizzazione (per poterlo fermare)
let isTracking = false;        // Flag booleano per indicare se il tracciamento è attivo
let sendInterval = null;       // Riferimento al timer che invia i dati periodicamente

let lastAcc = null;            // Ultimi dati di accelerazione registrati
let lastGyro = null;           // Ultimi dati del giroscopio registrati
let currentIntervalMs = 50;    // Intervallo di invio corrente (default 50ms = 20Hz)

let headingEstimator = new HeadingEstimator();
let signalProcessor = new SignalProcessor();
let fallDetector = new FallDetector();

let dataBuffer = [];
let flushInterval = null;
let t0 = null;
let lastGps = null;

let sosCountdownTimer = null;
let sosCountdownValue = 10;

let sessionId = null;          // ID univoco del turno di tracciamento corrente

// LOCK ATOMICO PER SOS
let sosLock = false;           // Impedisce riavvio multiplo vibrazione iniziale


// ==========================================
// GESTIONE DEI SENSORI DI MOVIMENTO
// ==========================================

// Funzione chiamata ad ogni evento di movimento del dispositivo
function handleMotion(e) {
    if (!isTracking) return;
    // Salva i dati dell'accelerazione (inclusa la gravità) se disponibili
    if (e.accelerationIncludingGravity) lastAcc = e.accelerationIncludingGravity;
    // Salva i dati di rotazione (giroscopio) se disponibili
    if (e.rotationRate) lastGyro = e.rotationRate;
}


// ==========================================
// COMUNICAZIONE CON IL SERVER (API)
// ==========================================



async function flushBuffer() {
    if (dataBuffer.length === 0) return;
    
    // Copia e svuota il buffer immediatamente
    const payload = [...dataBuffer];
    dataBuffer = [];
    
    try {
        const res = await fetch('/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            console.error("Errore invio dati:", res.status, await res.text());
        }
    } catch (err) {
        console.error("Errore invio dati:", err);
    }
}

// ==========================================
// GESTIONE DELL'ALLARME SOS E CONTO ALLA ROVESCIA
// ==========================================

// Avvia il conto alla rovescia locale
function startSOSCountdown() {
    if (sosCountdownTimer !== null || sosLock) return;
    sosLock = true;
    document.getElementById('crash-alert').style.display = 'flex';
    sosCountdownValue = 10;
    document.getElementById('timer-display').innerText = sosCountdownValue;
    if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 500]);

    sosCountdownTimer = setInterval(() => {
        sosCountdownValue -= 1;
        document.getElementById('timer-display').innerText = sosCountdownValue;
        if (sosCountdownValue > 0) {
            if (navigator.vibrate) navigator.vibrate(200);
        } else {
            clearInterval(sosCountdownTimer);
            sosCountdownTimer = null;
            sosLock = false;
            document.getElementById('crash-alert').style.display = 'none';
            alert("Notifica SOS inviata ai contatti d'emergenza!");
            fallDetector.confirmAlert();
            
            fetch('/trigger_sos', { method: 'POST' }).catch(console.error);
        }
    }, 1000);
}

// Annulla l'allarme SOS se l'utente preme il pulsante di smentita in tempo
function cancelSOS() {
    document.getElementById('crash-alert').style.display = 'none';
    sosLock = false;
    
    if (sosCountdownTimer !== null) {
        clearInterval(sosCountdownTimer);
        sosCountdownTimer = null;
    }
    
    fallDetector.resetAlert();
}


// ==========================================
// LOOP PRINCIPALE DI CAMPIONAMENTO
// ==========================================

// Eseguito a intervalli regolari per inviare gli ultimi dati memorizzati dei sensori
function tick() {
    if (!isTracking) return;
    if (t0 === null) t0 = Date.now();
    
    const time_sec = (Date.now() - t0) / 1000.0;
    let att = headingEstimator.isRunning ? headingEstimator.getAttitude() : {roll: 0, pitch: 0, yaw: 0};
    let heading = headingEstimator.isRunning ? headingEstimator.getHeading() : 0;
    
    let row = {
        time_sec: time_sec,
        acc_x: (lastAcc && lastAcc.x !== null) ? lastAcc.x : 0,
        acc_y: (lastAcc && lastAcc.y !== null) ? lastAcc.y : 0,
        acc_z: (lastAcc && lastAcc.z !== null) ? lastAcc.z : 0,
        gyro_x: (lastGyro && lastGyro.alpha !== null) ? lastGyro.alpha : 0,
        gyro_y: (lastGyro && lastGyro.beta !== null) ? lastGyro.beta : 0,
        gyro_z: (lastGyro && lastGyro.gamma !== null) ? lastGyro.gamma : 0,
        heading: heading,
        roll: att.roll,
        pitch: att.pitch,
        yaw: att.yaw,
        lat: lastGps ? lastGps.lat : null,
        lon: lastGps ? lastGps.lon : null,
        speed_kmh: lastGps ? lastGps.speed : null,
        gps_time: lastGps ? lastGps.time : null
    };

    row = signalProcessor.process(row);
    row = fallDetector.process(row);

    if (row.is_confirmed_fall) {
        startSOSCountdown();
    }

    // Al server viene inviato esclusivamente il sottoinsieme di campi richiesto dalla pipeline
    // (lat, lon, velocità, timestamp, esito fall detection, identità rider/sessione per il worker GPX):
    // nessun dato grezzo dei sensori.
    dataBuffer.push({
        rider_id: String(window.RIDER_ID),
        session_id: sessionId,
        lat: row.lat,
        lon: row.lon,
        speed_kmh: row.speed_kmh,
        timestamp: Date.now(),
        is_confirmed_fall: row.is_confirmed_fall,
        is_cancelled_fall: row.is_cancelled_fall
    });
}

// Modifica la frequenza di campionamento (es. per risparmiare batteria quando si è fermi)
function setSamplingRate(ms, force = false) {
    if (currentIntervalMs === ms && !force) return;
    currentIntervalMs = ms;

    // Riavvia l'intervallo con la nuova frequenza
    if (sendInterval !== null) {
        clearInterval(sendInterval);
        sendInterval = setInterval(tick, currentIntervalMs);
    }

    // Aggiorna il filtro con la nuova frequenza
    signalProcessor.setSamplingRate(1000.0 / ms);

    // Aggiorna l'interfaccia grafica in base allo stato (fermo o in movimento)
    const statusEl = document.getElementById('status');
    if (ms > 200) {
        statusEl.innerText = "Stato: Fermo / Semaforo (Risparmio Batteria 1Hz)";
        statusEl.style.backgroundColor = "#fff3cd";
    } else {
        statusEl.innerText = "Stato: In Movimento (Tracciamento 20Hz)";
        statusEl.style.backgroundColor = "#d4edda";
    }
}


// ==========================================
// AVVIO E ARRESTO DEL TRACCIAMENTO
// ==========================================

// Avvia il tracciamento dei sensori, del GPS e la comunicazione periodica
async function startTracking() {
    isTracking = true;
    sosLock = false;
    // Fallback per HTTP locale: crypto.randomUUID() esiste solo su HTTPS
    sessionId = (crypto && crypto.randomUUID) ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
    fallDetector.is_cancelled_fall = false;
    document.getElementById('btn-start').style.display = "none";
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').style.display = "inline-block";
    document.getElementById('btn-stop').disabled = false;
    setSamplingRate(50, true);
    t0 = Date.now();

    // Gestione dei permessi per i sensori su dispositivi iOS (Safari)
    let perm = await HeadingEstimator.requestPermissions();
    if (!perm && typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        alert('Permesso sensori non concesso.');
        stopTracking();
        return;
    }

    headingEstimator.start();

    // Registra l'ascoltatore per i movimenti del dispositivo
    window.addEventListener('devicemotion', handleMotion);

    // Avvia la geolocalizzazione per tracciare posizione e velocità
    if ('geolocation' in navigator) {
        watchId = navigator.geolocation.watchPosition((pos) => {
            if (isTracking) {
                lastGps = {
                    lat: pos.coords.latitude, 
                    lon: pos.coords.longitude,
                    speed: pos.coords.speed !== null ? pos.coords.speed * 3.6 : null,
                    time: pos.timestamp || Date.now()
                };
                
                // Regola dinamicamente la frequenza di campionamento in base alla velocità GPS
                if (pos.coords.speed !== null && pos.coords.speed !== undefined) {
                    if (pos.coords.speed < 0.6) {
                        setSamplingRate(1000); // Velocità molto bassa -> Risparmio batteria (1Hz)
                    } else {
                        setSamplingRate(50);   // In movimento -> Alta precisione (20Hz)
                    }
                }
            }
        }, (err) => console.error("Errore GPS:", err), { enableHighAccuracy: true });
    }

    // Avvia il timer principale per l'invio dei dati
    sendInterval = setInterval(tick, currentIntervalMs);
    flushInterval = setInterval(flushBuffer, 500);
}

// Ferma completamente il tracciamento e pulisce gli eventi/timer attivi
function stopTracking() {
    isTracking = false;
    window.removeEventListener('devicemotion', handleMotion);
    
    // Rimuove il controllo della posizione GPS
    if (watchId !== null && 'geolocation' in navigator) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }
    
    // Ferma l'invio periodico dei dati
    if (sendInterval !== null) {
        clearInterval(sendInterval);
        sendInterval = null;
    }
    
    if (flushInterval !== null) {
        clearInterval(flushInterval);
        flushInterval = null;
    }
    
    // Invia eventuali dati rimanenti, poi segnala al worker GPS la chiusura del turno
    flushBuffer().then(() => {
        if (sessionId !== null) {
            fetch('/session/end', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ rider_id: String(window.RIDER_ID), session_id: sessionId })
            }).then(res => {
                if (!res.ok) console.error("Errore chiusura sessione:", res.status);
            }).catch(err => console.error("Errore chiusura sessione:", err));
            sessionId = null;
        }
    });

    headingEstimator.stop();
    
    // Ripristina l'interfaccia grafica iniziale
    document.getElementById('btn-stop').style.display = "none";
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-start').style.display = "inline-block";
    document.getElementById('btn-start').disabled = false;
    document.getElementById('status').innerText = "Stato: Tracciamento fermato.";
    document.getElementById('status').style.backgroundColor = "#e0e0e0";
}