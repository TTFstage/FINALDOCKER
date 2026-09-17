/**
 * HeadingEstimator
 * Classe professionale per la fusione dati sensori (Giroscopio + Accelerometro + Bussola).
 *
 * ARCHITETTURA (v3, Madgwick):
 *  1) Filtro di Madgwick 6DOF (gyro + accelerometro) -> quaternione di assetto.
 *     Risolve alla radice il limite della versione precedente (integrazione sul
 *     solo asse Z del giroscopio, valida solo a device "in piano"): la cinematica
 *     quaternionica (qDot = 0.5 * q ⊗ [0,gx,gy,gz]) proietta correttamente la
 *     velocità angolare qualunque sia l'orientamento corrente, e la correzione a
 *     gradiente basata sull'accelerometro tiene allineati roll e pitch alla
 *     gravità reale in ogni istante.
 *  2) Correzione complementare solo sullo YAW, usando come riferimento assoluto
 *     webkitCompassHeading (iOS) o l'heading tilt-compensato calcolato da
 *     alpha/beta/gamma (Android). Il filtro di Madgwick da solo NON può fissare
 *     lo yaw: l'accelerometro non osserva la rotazione attorno all'asse di
 *     gravità, quindi senza correzione esterna lo yaw deriva nel tempo. Questo
 *     secondo stadio è necessario perché i browser non espongono in modo
 *     affidabile e cross-platform il magnetometro grezzo (mx,my,mz): niente
 *     vero MARG a 6 righe qui, solo eventi già processati dal SO.
 *
 * IMPORTANT VALIDATION NOTICE:
 * The sign/axis conventions (gyroscope flip on iOS, yaw -> compass heading
 * mapping, screenOffset) depend on browser and OS implementation details that
 * vary and are known to be subject to inconsistencies across versions. This code
 * follows the most common standard conventions but has NOT been validated on real
 * hardware in this session. Before production use: use getAttitude() to log
 * roll/pitch/yaw while manually rotating the device on each axis, and correct any
 * inverted signs.
 */

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;
const GRAVITY_MS2 = 9.80665;

class HeadingEstimator {
  /**
   * @param {Object} options
   * @param {number} [options.alpha=0.98] - Peso del giroscopio nella correzione
   *        complementare dello YAW (0-1). Più alto = più fiducia nel giroscopio,
   *        deriva corretta più lentamente verso il riferimento assoluto.
   * @param {number} [options.madgwickBeta=0.1] - Guadagno della correzione
   *        accelerometrica nel filtro di Madgwick (roll/pitch). Valore standard
   *        di partenza; va tarato in base al rumore reale del giroscopio target.
   * @param {number} [options.accelRejectionThreshold=0.15] - Frazione di
   *        scostamento da 1g oltre la quale la correzione accelerometrica viene
   *        attenuata/esclusa per il campione corrente (reiezione di accelerazioni
   *        lineari: se il device accelera, l'accelerometro non misura solo la
   *        gravità e non va usato come riferimento di "alto").
   * @param {number} [options.convergeMs=1000] - Durata della fase di
   *        convergenza rapida dopo l'inizializzazione, in cui il guadagno
   *        accelerometrico è amplificato per allineare velocemente roll/pitch.
   * @param {number} [options.fastBetaMultiplier=8] - Fattore di amplificazione
   *        di madgwickBeta durante la fase di convergenza rapida.
   * @param {function(number):void} [options.onUpdate] - Callback sincronizzata col frame rate.
   * @param {function(Object):void} [options.onStatusChange] - 'ok' | 'degraded'.
   * @param {number} [options.absoluteTimeoutMs=3000] - Timeout prima di passare
   *        in modalità degradata se non arriva mai un riferimento assoluto.
   */
  constructor({
    alpha = 0.98,
    madgwickBeta = 0.1,
    accelRejectionThreshold = 0.15,
    convergeMs = 1000,
    fastBetaMultiplier = 8,
    onUpdate = null,
    onStatusChange = null,
    absoluteTimeoutMs = 3000,
  } = {}) {
    this.alpha = alpha;
    this.madgwickBeta = madgwickBeta;
    this.accelRejectionThreshold = accelRejectionThreshold;
    this.convergeMs = convergeMs;
    this.fastBetaMultiplier = fastBetaMultiplier;
    this.onUpdate = onUpdate;
    this.onStatusChange = onStatusChange;
    this.absoluteTimeoutMs = absoluteTimeoutMs;

    // Quaternione di assetto: rotazione dal frame del device (body) al frame terrestre
    // (earth), convenzione Madgwick standard: v_earth = q ⊗ v_body ⊗ q_coniugato.
    this.quaternion = { w: 1, x: 0, y: 0, z: 0 };

    this.absoluteReference = null; // heading bussola in gradi, 0-360, o null se assente
    this.compassAccuracy = null; // solo iOS: webkitCompassAccuracy (negativo = non calibrato)
    this.lastTimestamp = null;
    this._initTimeAbs = null; // performance.now() al momento dell'inizializzazione (per fase rapida)
    this.isInitialized = false;
    this.isRunning = false;
    this.hasAbsoluteSource = false;
    this.degradedMode = false;

    // Inversione nota (empirica, non documentata ufficialmente) del segno della
    // velocity rate sull'asse Z (alpha) fra WebKit e Chromium. Applicata solo a
    // quell'asse: non ho conferma che lo stesso valga per beta/gamma, quindi non
    // la estendo per non introdurre un errore non verificato.
    this.isIOS = typeof navigator !== 'undefined' &&
                 /iPad|iPhone|iPod/.test(navigator.userAgent || '');

    this.screenOffset = this._getScreenOrientationAngle();

    this._orientationEventName = null;
    this._orientationIsAbsoluteByType = false;

    this._rafId = null;
    this._pendingUpdate = false;
    this._initTimeoutId = null;

    this._handleMotion = this._handleMotion.bind(this);
    this._handleOrientation = this._handleOrientation.bind(this);
    this._handleScreenOrientation = this._handleScreenOrientation.bind(this);
    this._triggerUpdate = this._triggerUpdate.bind(this);
  }

  /**
   * Richiede i permessi per accedere ai sensori (necessario solo su iOS 13+).
   * Da chiamare STRETTAMENTE in risposta a un'azione utente (es. click).
   * @returns {Promise<boolean>}
   */
  static async requestPermissions() {
    if (typeof window === 'undefined') return false;
    try {
      let motionGranted = true;
      let orientationGranted = true;

      if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        motionGranted = (await DeviceMotionEvent.requestPermission()) === 'granted';
      }
      if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
        orientationGranted = (await DeviceOrientationEvent.requestPermission()) === 'granted';
      }
      return motionGranted && orientationGranted;
    } catch (err) {
      console.error('[HeadingEstimator] Errore richiesta permessi:', err);
      return false;
    }
  }

  start() {
    if (this.isRunning || typeof window === 'undefined') return;
    this.isRunning = true;
    this.isInitialized = false;
    this.lastTimestamp = null;
    this._initTimeAbs = null;
    this.absoluteReference = null;
    this.hasAbsoluteSource = false;
    this.degradedMode = false;
    this.quaternion = { w: 1, x: 0, y: 0, z: 0 };

    window.addEventListener('devicemotion', this._handleMotion, { passive: true });

    if ('ondeviceorientationabsolute' in window) {
      this._orientationEventName = 'deviceorientationabsolute';
      this._orientationIsAbsoluteByType = true;
    } else {
      this._orientationEventName = 'deviceorientation';
      this._orientationIsAbsoluteByType = false;
    }
    window.addEventListener(this._orientationEventName, this._handleOrientation, { passive: true });

    const orientationTarget = screen.orientation || window;
    const orientationEvent = screen.orientation ? 'change' : 'orientationchange';
    orientationTarget.addEventListener(orientationEvent, this._handleScreenOrientation, { passive: true });

    // Evita il deadlock: se entro absoluteTimeoutMs non arriva nessun riferimento
    // assoluto valido, inizializza comunque in modalità degradata (yaw da solo
    // giroscopio, quindi soggetto a deriva) invece di restare bloccati.
    this._initTimeoutId = setTimeout(() => this._fallbackInitWithoutAbsolute(), this.absoluteTimeoutMs);
  }

  stop() {
    if (!this.isRunning) return;
    this.isRunning = false;

    window.removeEventListener('devicemotion', this._handleMotion);
    if (this._orientationEventName) {
      window.removeEventListener(this._orientationEventName, this._handleOrientation);
    }

    const orientationTarget = screen.orientation || window;
    const orientationEvent = screen.orientation ? 'change' : 'orientationchange';
    orientationTarget.removeEventListener(orientationEvent, this._handleScreenOrientation);

    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    this._clearInitTimeout();
  }

  /**
   * Heading corrente in gradi [0, 360), compensato per la rotazione dello schermo.
   */
  getHeading() {
    return HeadingEstimator.normalize360(this._getYawHeadingDeg() + this.screenOffset);
  }

  /**
   * Assetto completo in gradi (roll, pitch, yaw — convenzione aeronautica ZYX),
   * utile principalmente per debug/validazione della fusione, non per l'uso
   * bussola in sé (che usa getHeading()).
   */
  getAttitude() {
    const q = this.quaternion;
    const roll = Math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y));
    const sinPitch = Math.max(-1, Math.min(1, 2 * (q.w * q.y - q.z * q.x)));
    const pitch = Math.asin(sinPitch);
    const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
    return { roll: roll * RAD2DEG, pitch: pitch * RAD2DEG, yaw: yaw * RAD2DEG };
  }

  getStatus() {
    return {
      isInitialized: this.isInitialized,
      hasAbsoluteSource: this.hasAbsoluteSource,
      degradedMode: this.degradedMode,
      compassAccuracy: this.compassAccuracy,
    };
  }

  // ==========================================
  // METODI PRIVATI - SENSOR FUSION
  // ==========================================

  _handleMotion(event) {
    if (!this.isRunning || !event.rotationRate) return;

    let dt = 0;
    if (event.interval) {
      dt = event.interval / 1000;
    } else {
      const now = event.timeStamp || performance.now();
      if (!this.lastTimestamp) {
        this.lastTimestamp = now;
        return;
      }
      dt = (now - this.lastTimestamp) / 1000;
      this.lastTimestamp = now;
    }
    if (dt <= 0 || dt > 0.1) return; // filtro antispike (tab in background, ecc.)

    if (!this.isInitialized) return; // aspetta un riferimento assoluto o il timeout di fallback

    // Velocità angolari in rad/s. rotationRate: alpha=asse Z (yaw), beta=asse X
    // (pitch), gamma=asse Y (roll) — stessa convenzione di DeviceOrientationEvent.
    let gz = (event.rotationRate.alpha || 0) * DEG2RAD;
    const gx = (event.rotationRate.beta || 0) * DEG2RAD;
    const gy = (event.rotationRate.gamma || 0) * DEG2RAD;
    if (this.isIOS) gz = -gz;

    // Accelerometer gain: amplified to converge after init to quickly
    // align roll/pitch, then returns to base value.
    let beta = this.madgwickBeta;
    if (this._initTimeAbs !== null) {
      const elapsed = performance.now() - this._initTimeAbs;
      if (elapsed < this.convergeMs) {
        const t = elapsed / this.convergeMs;
        beta = this.madgwickBeta * this.fastBetaMultiplier * (1 - t) + this.madgwickBeta * t;
      }
    }

    const acc = event.accelerationIncludingGravity;
    if (acc && typeof acc.x === 'number') {
      this._madgwickIMUUpdate(gx, gy, gz, acc.x, acc.y, acc.z, dt, beta);
    } else {
      // Nessun accelerometro disponibile: integrazione gyro-only sull'intero
      // quaternione (comunque cinematicamente corretta, ma priva di ancoraggio
      // alla gravità: roll/pitch derivano nel tempo senza limite).
      this._integrateGyroOnly(gx, gy, gz, dt);
    }

    // Correzione complementare dello yaw verso il riferimento assoluto.
    if (this.absoluteReference !== null) {
      const currentHeading = this._getYawHeadingDeg();
      const error = HeadingEstimator.normalize180(this.absoluteReference - currentHeading);
      this._applyYawCorrectionDeg((1 - this.alpha) * error);
    }

    if (this.onUpdate && !this._pendingUpdate) {
      this._pendingUpdate = true;
      this._rafId = requestAnimationFrame(this._triggerUpdate);
    }
  }

  /**
   * Un passo del filtro di Madgwick IMU (gyro + accelerometro). Aggiorna
   * this.quaternion. Jacobiano derivato direttamente dalle derivate parziali
   * delle formule di rotazione quaternionica (verificato per differenziazione
   * diretta, non trascritto da un formulario a memoria).
   */
  _madgwickIMUUpdate(gx, gy, gz, ax, ay, az, dt, beta) {
    const q = this.quaternion;

    // Predizione cinematica da giroscopio: qDot = 0.5 * q ⊗ [0, gx, gy, gz]
    const qDot = {
      w: 0.5 * (-q.x * gx - q.y * gy - q.z * gz),
      x: 0.5 * (q.w * gx + q.y * gz - q.z * gy),
      y: 0.5 * (q.w * gy - q.x * gz + q.z * gx),
      z: 0.5 * (q.w * gz + q.x * gy - q.y * gx),
    };

    const accelNorm = Math.sqrt(ax * ax + ay * ay + az * az);
    if (accelNorm > 1e-6 && beta > 0) {
      // Reiezione di accelerazioni lineari: se il modulo si discosta troppo da 1g,
      // l'accelerometro non sta misurando (solo) la gravità in questo campione.
      const deviation = Math.abs(accelNorm - GRAVITY_MS2) / GRAVITY_MS2;
      const accelWeight = Math.max(0, 1 - deviation / this.accelRejectionThreshold);

      if (accelWeight > 0) {
        const nAx = ax / accelNorm, nAy = ay / accelNorm, nAz = az / accelNorm;

        // Funzione obiettivo: differenza fra la direzione di gravità prevista dal
        // quaternione corrente e quella misurata dall'accelerometro.
        const f1 = 2 * (q.x * q.z - q.w * q.y) - nAx;
        const f2 = 2 * (q.w * q.x + q.y * q.z) - nAy;
        const f3 = 2 * (0.5 - q.x * q.x - q.y * q.y) - nAz;

        // Gradiente = J^T * F
        const grad = {
          w: -2 * q.y * f1 + 2 * q.x * f2,
          x: 2 * q.z * f1 + 2 * q.w * f2 - 4 * q.x * f3,
          y: -2 * q.w * f1 + 2 * q.z * f2 - 4 * q.y * f3,
          z: 2 * q.x * f1 + 2 * q.y * f2,
        };
        const gradNorm = Math.sqrt(grad.w * grad.w + grad.x * grad.x + grad.y * grad.y + grad.z * grad.z);
        if (gradNorm > 1e-9) {
          const scale = (beta * accelWeight) / gradNorm;
          qDot.w -= grad.w * scale;
          qDot.x -= grad.x * scale;
          qDot.y -= grad.y * scale;
          qDot.z -= grad.z * scale;
        }
      }
    }

    const integrated = {
      w: q.w + qDot.w * dt,
      x: q.x + qDot.x * dt,
      y: q.y + qDot.y * dt,
      z: q.z + qDot.z * dt,
    };
    this.quaternion = HeadingEstimator.quatNormalize(integrated);
  }

  _integrateGyroOnly(gx, gy, gz, dt) {
    const q = this.quaternion;
    const qDot = {
      w: 0.5 * (-q.x * gx - q.y * gy - q.z * gz),
      x: 0.5 * (q.w * gx + q.y * gz - q.z * gy),
      y: 0.5 * (q.w * gy - q.x * gz + q.z * gx),
      z: 0.5 * (q.w * gz + q.x * gy - q.y * gx),
    };
    this.quaternion = HeadingEstimator.quatNormalize({
      w: q.w + qDot.w * dt,
      x: q.x + qDot.x * dt,
      y: q.y + qDot.y * dt,
      z: q.z + qDot.z * dt,
    });
  }

  /**
   * Applica una rotazione aggiuntiva attorno all'asse Z del frame terrestre per
   * correggere lo yaw di correctionDeg gradi, lasciando roll/pitch inalterati.
   */
  _applyYawCorrectionDeg(correctionDeg) {
    if (Math.abs(correctionDeg) < 1e-6) return;
    const dYawRad = this._headingDegToYawRad(correctionDeg) - this._headingDegToYawRad(0);
    const qCorr = HeadingEstimator.quatFromYaw(dYawRad);
    this.quaternion = HeadingEstimator.quatNormalize(HeadingEstimator.quatMultiply(qCorr, this.quaternion));
  }

  _getYawHeadingDeg() {
    const q = this.quaternion;
    const yawRad = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
    return this._yawRadToHeadingDeg(yawRad);
  }

  // Conversione fra yaw interno (radianti, convenzione quaternioni standard,
  // positivo antiorario visto dall'alto) e heading bussola (gradi, positivo
  // orario, 0 = Nord). Segno da validare sul device reale (vedi avviso in testa
  // al file).
  _yawRadToHeadingDeg(yawRad) {
    return HeadingEstimator.normalize360(-yawRad * RAD2DEG);
  }

  _headingDegToYawRad(headingDeg) {
    return -headingDeg * DEG2RAD;
  }

  // ==========================================
  // METODI PRIVATI - RIFERIMENTO ASSOLUTO (BUSSOLA)
  // ==========================================

  _handleOrientation(event) {
    if (!this.isRunning) return;

    // --- iOS: webkitCompassHeading è già tilt-compensato dal SO. ---
    if (typeof event.webkitCompassHeading === 'number' && !Number.isNaN(event.webkitCompassHeading)) {
      if (typeof event.webkitCompassAccuracy === 'number') {
        this.compassAccuracy = event.webkitCompassAccuracy;
      }
      this._setAbsoluteReference(event.webkitCompassHeading);
      return;
    }

    // --- Android / standard W3C DeviceOrientation ---
    const isAbsolute = this._orientationIsAbsoluteByType || event.absolute === true;
    if (!isAbsolute) return;
    if (event.alpha === null || event.beta === null || event.gamma === null) return;

    const heading = HeadingEstimator.computeTiltCompensatedHeading(event.alpha, event.beta, event.gamma);
    this._setAbsoluteReference(heading);
  }

  _setAbsoluteReference(heading) {
    this.absoluteReference = heading;
    if (!this.hasAbsoluteSource) this.hasAbsoluteSource = true;

    if (!this.isInitialized) {
      // Inizializzo il quaternione con yaw allineato al riferimento assoluto e
      // roll/pitch a zero: convergeranno rapidamente grazie al beta amplificato
      // nella fase di convergenza (vedi _handleMotion).
      this.quaternion = HeadingEstimator.quatFromYaw(this._headingDegToYawRad(heading));
      this.isInitialized = true;
      this._initTimeAbs = performance.now();
      this._clearInitTimeout();
      this._emitStatus('ok');
      return;
    }

    if (this.degradedMode) {
      this.degradedMode = false;
      this._emitStatus('ok');
    }
  }

  _fallbackInitWithoutAbsolute() {
    this._initTimeoutId = null;
    if (this.isInitialized || !this.isRunning) return;

    this.quaternion = { w: 1, x: 0, y: 0, z: 0 };
    this.isInitialized = true;
    this._initTimeAbs = performance.now();
    this.degradedMode = true;
    this._emitStatus(
      'degraded',
      'Nessun riferimento assoluto (bussola) ricevuto in tempo: yaw da solo giroscopio, soggetto a deriva.'
    );
  }

  _clearInitTimeout() {
    if (this._initTimeoutId !== null) {
      clearTimeout(this._initTimeoutId);
      this._initTimeoutId = null;
    }
  }

  _emitStatus(state, message) {
    if (this.onStatusChange) {
      this.onStatusChange({
        state,
        message,
        isInitialized: this.isInitialized,
        hasAbsoluteSource: this.hasAbsoluteSource,
      });
    }
  }

  _triggerUpdate() {
    this._pendingUpdate = false;
    if (this.onUpdate) this.onUpdate(this.getHeading());
  }

  _handleScreenOrientation() {
    this.screenOffset = this._getScreenOrientationAngle();
  }

  _getScreenOrientationAngle() {
    if (typeof screen !== 'undefined' && screen.orientation && typeof screen.orientation.angle === 'number') {
      return screen.orientation.angle;
    }
    if (typeof window !== 'undefined' && typeof window.orientation === 'number') {
      return window.orientation;
    }
    return 0;
  }

  // ==========================================
  // UTILITY - QUATERNIONI E ANGOLI
  // ==========================================

  static quatMultiply(a, b) {
    return {
      w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
      x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
      y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
      z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
    };
  }

  static quatNormalize(q) {
    const norm = Math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
    if (norm < 1e-9) return { w: 1, x: 0, y: 0, z: 0 };
    return { w: q.w / norm, x: q.x / norm, y: q.y / norm, z: q.z / norm };
  }

  static quatFromYaw(yawRad) {
    const half = yawRad / 2;
    return { w: Math.cos(half), x: 0, y: 0, z: Math.sin(half) };
  }

  /**
   * Heading tilt-compensato a partire da alpha/beta/gamma (gradi, convenzione
   * W3C DeviceOrientation), usato per il riferimento assoluto su Android.
   * Proietta il vettore "nord" sul piano orizzontale reale del device.
   */
  static computeTiltCompensatedHeading(alphaDeg, betaDeg, gammaDeg) {
    const alpha = alphaDeg * DEG2RAD;
    const beta = betaDeg * DEG2RAD;
    const gamma = gammaDeg * DEG2RAD;

    const cA = Math.cos(alpha), sA = Math.sin(alpha);
    const cB = Math.cos(beta), sB = Math.sin(beta);
    const cG = Math.cos(gamma), sG = Math.sin(gamma);

    const Vx = -cA * sG - sA * sB * cG;
    const Vy = -sA * sG + cA * sB * cG;

    const heading = Math.atan2(Vx, Vy) * RAD2DEG;
    return HeadingEstimator.normalize360(heading);
  }

  static normalize180(angle) {
    let a = angle % 360;
    if (a >= 180) a -= 360;
    if (a < -180) a += 360;
    return a;
  }

  static normalize360(angle) {
    return (angle % 360 + 360) % 360;
  }
}
