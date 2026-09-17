// ==========================================
// STATE VARIABLES AND CONFIGURATION
// ==========================================
let watchId = null;            // Geolocation sensor ID (to be able to stop it)
let isTracking = false;        // Boolean flag indicating whether tracking is active
let sendInterval = null;       // Reference to the timer that periodically sends data

let lastAcc = null;            // Last recorded acceleration data
let lastGyro = null;           // Last recorded gyroscope data
let currentIntervalMs = 50;    // Current sending interval (default 50ms = 20Hz)

let headingEstimator = new HeadingEstimator();
let signalProcessor = new SignalProcessor();
let fallDetector = new FallDetector();

let dataBuffer = [];
let flushInterval = null;
let t0 = null;
let lastGps = null;

let sosCountdownTimer = null;
let sosCountdownValue = 10;

let sessionId = null;          // Unique ID of the current tracking session

// ATOMIC LOCK FOR SOS
let sosLock = false;           // Prevents multiple restarts of the initial vibration


// ==========================================
// MOTION SENSOR MANAGEMENT
// ==========================================

// Function called on every device motion event
function handleMotion(e) {
    if (!isTracking) return;
    // Save acceleration data (including gravity) if available
    if (e.accelerationIncludingGravity) lastAcc = e.accelerationIncludingGravity;
    // Save rotation data (gyroscope) if available
    if (e.rotationRate) lastGyro = e.rotationRate;
}


// ==========================================
// SERVER COMMUNICATION (API)
// ==========================================



async function flushBuffer() {
    if (dataBuffer.length === 0) return;
    
    // Copy and immediately clear the buffer
    const payload = [...dataBuffer];
    dataBuffer = [];
    
    try {
        const res = await fetch('/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            console.error("Error sending data:", res.status, await res.text());
        }
    } catch (err) {
        console.error("Error sending data:", err);
    }
}

// ==========================================
// SOS ALARM AND COUNTDOWN MANAGEMENT
// ==========================================

// Start the local countdown
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
            alert("SOS notification sent to emergency contacts!");
            fallDetector.confirmAlert();
            
            fetch('/trigger_sos', { method: 'POST' }).catch(console.error);
        }
    }, 1000);
}

// Cancel the SOS alarm if the user presses the cancel button in time
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
// MAIN SAMPLING LOOP
// ==========================================

// Executed at regular intervals to send the latest stored sensor data
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

    // Only the subset of fields required by the pipeline is sent to the server
    // (lat, lon, speed, timestamp, fall detection result, rider/session identity for GPX worker):
    // no raw sensor data is sent.
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

// Change the sampling rate (e.g. to save battery when stationary)
function setSamplingRate(ms, force = false) {
    if (currentIntervalMs === ms && !force) return;
    currentIntervalMs = ms;

    // Restart the interval with the new rate
    if (sendInterval !== null) {
        clearInterval(sendInterval);
        sendInterval = setInterval(tick, currentIntervalMs);
    }

    // Update the filter with the new sampling rate
    signalProcessor.setSamplingRate(1000.0 / ms);

    // Update the UI based on state (stopped or moving)
    const statusEl = document.getElementById('status');
    if (ms > 200) {
        statusEl.innerText = "Status: Stopped / Traffic light (Battery saving 1Hz)";
        statusEl.style.backgroundColor = "#fff3cd";
    } else {
        statusEl.innerText = "Status: Moving (Tracking 20Hz)";
        statusEl.style.backgroundColor = "#d4edda";
    }
}


// ==========================================
// START AND STOP TRACKING
// ==========================================

// Start tracking sensors, GPS and periodic communication
async function startTracking() {
    isTracking = true;
    sosLock = false;
    // Fallback for local HTTP: crypto.randomUUID() only exists on HTTPS
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

    // Handle sensor permissions on iOS devices (Safari)
    let perm = await HeadingEstimator.requestPermissions();
    if (!perm && typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        alert('Sensor permission not granted.');
        stopTracking();
        return;
    }

    headingEstimator.start();

    // Register the device motion event listener
    window.addEventListener('devicemotion', handleMotion);

    // Start geolocation to track position and speed
    if ('geolocation' in navigator) {
        watchId = navigator.geolocation.watchPosition((pos) => {
            if (isTracking) {
                lastGps = {
                    lat: pos.coords.latitude, 
                    lon: pos.coords.longitude,
                    speed: pos.coords.speed !== null ? pos.coords.speed * 3.6 : null,
                    time: pos.timestamp || Date.now()
                };
                
                // Dynamically adjust the sampling rate based on GPS speed
                if (pos.coords.speed !== null && pos.coords.speed !== undefined) {
                    if (pos.coords.speed < 0.6) {
                        setSamplingRate(1000); // Very low speed -> Battery saving (1Hz)
                    } else {
                        setSamplingRate(50);   // Moving -> High precision (20Hz)
                    }
                }
            }
        }, (err) => console.error("GPS error:", err), { enableHighAccuracy: true });
    }

    // Start the main data sending timer
    sendInterval = setInterval(tick, currentIntervalMs);
    flushInterval = setInterval(flushBuffer, 500);
}

// Completely stop tracking and clean up active events/timers
function stopTracking() {
    isTracking = false;
    window.removeEventListener('devicemotion', handleMotion);
    
    // Remove the GPS position watch
    if (watchId !== null && 'geolocation' in navigator) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }
    
    // Stop the periodic data sending
    if (sendInterval !== null) {
        clearInterval(sendInterval);
        sendInterval = null;
    }
    
    if (flushInterval !== null) {
        clearInterval(flushInterval);
        flushInterval = null;
    }
    
    // Send any remaining data, then signal the GPS worker to close the session
    flushBuffer().then(() => {
        if (sessionId !== null) {
            fetch('/session/end', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ rider_id: String(window.RIDER_ID), session_id: sessionId })
            }).then(res => {
                if (!res.ok) console.error("Session close error:", res.status);
            }).catch(err => console.error("Session close error:", err));
            sessionId = null;
        }
    });

    headingEstimator.stop();
    
    // Restore the initial UI state
    document.getElementById('btn-stop').style.display = "none";
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-start').style.display = "inline-block";
    document.getElementById('btn-start').disabled = false;
    document.getElementById('status').innerText = "Status: Tracking stopped.";
    document.getElementById('status').style.backgroundColor = "#e0e0e0";
}