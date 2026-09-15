from flask import Blueprint, render_template, request
from flask_security import current_user
from app.auth.models import Group, GroupMembership

pages_bp = Blueprint("map_pages", __name__, url_prefix="/map")


@pages_bp.get("/")
def home():
    return render_template("map/home.html")


@pages_bp.get("/app")
def app_map():
    group_id = request.args.get('group_id', type=int)
    members = []
    if group_id and current_user.is_authenticated:
        # Verifica che l'utente faccia parte del gruppo
        membership = GroupMembership.query.filter_by(
            user_id=current_user.id, group_id=group_id
        ).first()
        if membership:
            members = GroupMembership.query.filter_by(group_id=group_id).all()
    
    return render_template("map/map.html", group_id=group_id, members=members)
