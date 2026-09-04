class SignalProcessor {
    constructor() {
        this.fs = 20.0;
        this.dt = 1.0 / this.fs;
        
        this.state = {
            acc_x: 0, acc_y: 0, acc_z: 0,
            gyro_x: 0, gyro_y: 0, gyro_z: 0
        };
        this.initialized = false;

        this.last_acc_mag = null;
        
        // Per calcolo roughness (finestra 2s = 40 campioni)
        this.acc_z_history = [];
        this.roughness_window = parseInt(this.fs * 2.0);

        // Per calcolo velocità GPS
        this.last_gps_pos = null;
        this.current_speed_kmh = 0.0;
        this._updateAlpha();
    }

    setSamplingRate(fs) {
        this.fs = fs;
        this.dt = 1.0 / this.fs;
        this._updateAlpha();
    }

    _updateAlpha() {
        let fc = Math.min(4.0, this.fs / 2.1); 
        let RC = 1.0 / (2.0 * Math.PI * fc);
        this.alpha = this.dt / (RC + this.dt);
    }

    _filterValue(key, val) {
        if (!this.initialized) {
            this.state[key] = val;
        } else {
            this.state[key] = this.alpha * val + (1 - this.alpha) * this.state[key];
        }
        return this.state[key];
    }

    process(row) {
        // Applica i filtri
        let fx = this._filterValue('acc_x', row.acc_x);
        let fy = this._filterValue('acc_y', row.acc_y);
        let fz = this._filterValue('acc_z', row.acc_z);
        
        let gx = this._filterValue('gyro_x', row.gyro_x);
        let gy = this._filterValue('gyro_y', row.gyro_y);
        let gz = this._filterValue('gyro_z', row.gyro_z);
        
        this.initialized = true;

        // Magnitudo
        row.acc_magnitude = Math.sqrt(fx*fx + fy*fy + fz*fz);
        row.gyro_magnitude = Math.sqrt(gx*gx + gy*gy + gz*gz);

        // Jerk
        if (this.last_acc_mag !== null) {
            row.jerk = (row.acc_magnitude - this.last_acc_mag) / this.dt;
        } else {
            row.jerk = 0.0;
        }
        this.last_acc_mag = row.acc_magnitude;

        // Roughness (deviazione standard acc_z)
        this.acc_z_history.push(fz);
        if (this.acc_z_history.length > this.roughness_window) {
            this.acc_z_history.shift();
        }
        
        let mean_z = this.acc_z_history.reduce((a, b) => a + b, 0) / this.acc_z_history.length;
        let var_z = this.acc_z_history.reduce((a, b) => a + Math.pow(b - mean_z, 2), 0) / this.acc_z_history.length;
        row.roughness = Math.sqrt(var_z);

        // Velocità
        if (row.speed_kmh !== undefined && row.speed_kmh !== null) {
            this.current_speed_kmh = row.speed_kmh;
        } else if (row.lat !== null && row.lon !== null && row.gps_time !== undefined) {
            if (this.last_gps_pos !== null && this.last_gps_pos.time !== row.gps_time) {
                let dlat = row.lat - this.last_gps_pos.lat;
                let dlon = row.lon - this.last_gps_pos.lon;
                let dt_sec = (row.gps_time - this.last_gps_pos.time) / 1000.0;
                
                if (dt_sec > 0) {
                    let vy = (dlat / dt_sec) * 111320.0;
                    let vx = (dlon / dt_sec) * 111320.0 * Math.cos(row.lat * Math.PI / 180.0);
                    this.current_speed_kmh = Math.sqrt(vx*vx + vy*vy) * 3.6;
                }
            }
            this.last_gps_pos = {lat: row.lat, lon: row.lon, time: row.gps_time};
        }
        row.speed_kmh = this.current_speed_kmh;

        return row;
    }
}
