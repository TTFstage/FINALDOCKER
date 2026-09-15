class FallDetector {
    constructor() {
        this.BASE_IMPACT_THRESHOLD = 30.0;
        this.JERK_THRESHOLD = 250.0;
        this.ROTATION_THRESHOLD = 200.0;
        this.STOPPED_SPEED_KMH = 3.5;
        this.ROUGHNESS_PAVE_THRESHOLD = 3.5;
        this.PAVE_IMPACT_MULTIPLIER = 1.4;

        this.ROTATION_WINDOW_SEC = 1.0;
        this.IMMOBILITY_WINDOW_SEC = 3.0;
        this.CRASH_COOLDOWN_SEC = 12.0;

        this.pending_alert = false;
        this.last_crash_system_time = 0.0;
        this.potential_falls = [];
        this.is_cancelled_fall = false;
        this.last_confirmed_t_impact = null;
        this.cancelled_t_impact = null;

        this.history = [];
        this.HISTORY_LEN = 300;
    }

    _registerImpacts(row) {
        let dyn_thresh = this.BASE_IMPACT_THRESHOLD * (
            row.roughness > this.ROUGHNESS_PAVE_THRESHOLD ? this.PAVE_IMPACT_MULTIPLIER : 1.0
        );

        if (row.acc_magnitude >= dyn_thresh && Math.abs(row.jerk) >= this.JERK_THRESHOLD) {
            this.potential_falls.push({
                t_impact: row.time_sec,
                g: row.acc_magnitude,
                jerk: row.jerk
            });
        }
    }

    _isConfirmedFall(t_imp) {
        let post_impact_data = this.history.filter(r => r.time_sec >= t_imp);

        let rot_window = post_impact_data.filter(r => r.time_sec <= t_imp + this.ROTATION_WINDOW_SEC);
        let has_rotation = rot_window.some(r => r.gyro_magnitude >= this.ROTATION_THRESHOLD);

        let imm_window = post_impact_data.filter(r => r.time_sec > t_imp + 0.5 && r.time_sec <= t_imp + this.IMMOBILITY_WINDOW_SEC);

        let is_immobile = false;
        if (imm_window.length > 0) {
            let mean_speed = imm_window.reduce((sum, r) => sum + r.speed_kmh, 0) / imm_window.length;
            is_immobile = mean_speed <= this.STOPPED_SPEED_KMH;
        }

        return has_rotation && is_immobile;
    }

    process(row) {
        this.history.push(row);
        if (this.history.length > this.HISTORY_LEN) {
            this.history.shift();
        }

        row.is_confirmed_fall = this.pending_alert;
        row.is_cancelled_fall = this.is_cancelled_fall;
        row.cancelled_t_impact = this.cancelled_t_impact;

        // flag one-shot: non deve restare appiccicato alle righe successive
        if (this.is_cancelled_fall) {
            this.is_cancelled_fall = false;
            this.cancelled_t_impact = null;
        }

        this._registerImpacts(row);

        let now_sys_time = Date.now() / 1000.0;
        let remaining_falls = [];

        for (let fall of this.potential_falls) {
            let t_imp = fall.t_impact;
            let in_cooldown = (now_sys_time - this.last_crash_system_time) < this.CRASH_COOLDOWN_SEC;

            if (in_cooldown || this.pending_alert) {
                if (row.time_sec < (t_imp + this.IMMOBILITY_WINDOW_SEC)) {
                    remaining_falls.push(fall);
                }
                continue;
            }

            if (row.time_sec < (t_imp + this.IMMOBILITY_WINDOW_SEC)) {
                remaining_falls.push(fall);
                continue;
            }

            if (this._isConfirmedFall(t_imp)) {
                row.is_confirmed_fall = true;
                this.pending_alert = true;
                this.last_crash_system_time = now_sys_time;
                this.last_confirmed_t_impact = t_imp;
                console.warn(`🚨 CADUTA CONFERMATA al sec ${t_imp.toFixed(1)}! (Jerk=${fall.jerk.toFixed(1)})`);
            }
        }

        this.potential_falls = remaining_falls;
        return row;
    }

    resetAlert() {
        this.pending_alert = false;
        this.is_cancelled_fall = true;
        this.cancelled_t_impact = this.last_confirmed_t_impact;
    }

    confirmAlert() {
        this.pending_alert = false;
    }
}