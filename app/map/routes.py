from flask import Blueprint, render_template, request
from flask_security import current_user

from app.auth.models import GroupMembership

pages_bp = Blueprint("map_pages", __name__, url_prefix="/map")


@pages_bp.get("/")
def home():
    group_id = request.args.get('group_id', type=int)
    members = []
    if group_id and current_user.is_authenticated:
        # Verify that the user belongs to the group
        membership = GroupMembership.query.filter_by(
            user_id=current_user.id, group_id=group_id
        ).first()
        if membership:
            members = GroupMembership.query.filter_by(group_id=group_id).all()
    
    return render_template("map/map.html", group_id=group_id, members=members)
