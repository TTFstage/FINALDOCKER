from flask import Blueprint

other_bp = Blueprint('other', __name__)

from app.other import routes  # noqa: E402, F401
