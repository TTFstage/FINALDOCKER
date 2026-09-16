from flask import Blueprint, render_template, abort
from flask_security import auth_required, current_user
from app.auth.models import RiderShift
import os

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/')
@auth_required()
def index():
    # Recupera tutti i turni con GPX validi dell'utente loggato
    shifts = RiderShift.query.filter(
        RiderShift.user_id == current_user.id,
        RiderShift.gpx_path.isnot(None),
        RiderShift.gpx_path != ''
    ).order_by(RiderShift.created_at.desc()).all()
    
    # Filtriamo quelli in cui il file esiste davvero su disco, se desiderato
    valid_shifts = []
    for shift in shifts:
        if os.path.exists(shift.gpx_path):
            valid_shifts.append(shift)
            
    return render_template('analytics/index.html', shifts=valid_shifts)
