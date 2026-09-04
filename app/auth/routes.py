from flask import Blueprint, flash, redirect, render_template, url_for
from flask_security import auth_required, current_user, logout_user

from extensions import db, security

auth_bp = Blueprint('auth', __name__)

@auth_bp.get("/me")
@auth_required()
def me():
    return render_template(
        "auth/private_page.html",
        username=current_user.username, 
        phone_number=current_user.phone_number,
        email=current_user.email
    )

@auth_bp.post("/delete_account")
@auth_required()
def delete_account():
    # Save the reference before logout
    user_to_delete = current_user._get_current_object()
    try:
        logout_user()
        security.datastore.delete_user(user_to_delete)
        db.session.commit()
        flash("Account eliminato con successo.", "info")
        return redirect(url_for("core.index"))
    except Exception:  # noqa: BLE001
        db.session.rollback()
        flash("Impossibile eliminare l'account. Riprova più tardi.", "error")
        # Since the user is logged out if it reaches here and fails, redirecting to index is safer
        # Or we can just redirect to index anyway if there's an error.
        return redirect(url_for("core.index"))
