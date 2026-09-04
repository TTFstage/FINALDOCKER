import os

from flask import Blueprint, abort, render_template, send_file
from flask_security import current_user, login_required

from app.auth.models import FallEvent, RiderShift

core_bp = Blueprint('core', __name__)

@core_bp.route("/")
def index():
    shifts = []
    falls = []
    if current_user.is_authenticated:
        shifts = RiderShift.query.filter_by(user_id=current_user.id).order_by(RiderShift.created_at.desc()).all()
        falls = FallEvent.query.filter_by(user_id=current_user.id).order_by(FallEvent.timestamp.desc()).all()
    return render_template("core/index.html", user=current_user, shifts=shifts, falls=falls)

@core_bp.route("/download/gpx/<int:shift_id>")
@login_required
def download_gpx(shift_id):
    shift = RiderShift.query.get_or_404(shift_id)
    if shift.user_id != current_user.id:
        abort(403)
        
    gpx_path = shift.gpx_path
    if not os.path.exists(gpx_path):
        abort(404, description="Il file GPX non è ancora stato generato o è stato rimosso.")
        
    return send_file(gpx_path, as_attachment=True, download_name=f"session_{shift.session_id}.gpx")
