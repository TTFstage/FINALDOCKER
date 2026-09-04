from flask import Blueprint

group_bp = Blueprint('group', __name__, url_prefix='/groups')

from app.group import routes  # noqa: F401
