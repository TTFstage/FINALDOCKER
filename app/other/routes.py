from flask import render_template
from flask_security import auth_required

from app.other import other_bp


@other_bp.route('/')
@auth_required()
def index():
    """Hub page with links to Profile and Groups."""
    return render_template('other/index.html')
