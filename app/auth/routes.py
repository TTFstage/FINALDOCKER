from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user, logout_user

from app.auth.forms import SOSContactForm
from app.auth.models import SOSContact
from extensions import db, security

auth_bp = Blueprint('auth', __name__)


@auth_bp.get("/check_session")
@auth_required()
def check_session():
    """Returns the current user id if the session cookie is valid."""
    from flask import jsonify
    return jsonify({"user_id": current_user.id, "authenticated": True})


@auth_bp.get("/me")
@auth_required()
def me():
    """User profile page: data, logout and account deletion."""
    return render_template(
        "auth/private_page.html",
        username=current_user.username,
        phone_number=current_user.phone_number,
        email=current_user.email,
        tax_id_code=current_user.tax_id_code,
        full_name=current_user.full_name,
        date_of_birth=current_user.date_of_birth,
        gender=current_user.gender,
        birth_city_country=current_user.birth_city_country,
    )


@auth_bp.post("/delete_account")
@auth_required()
def delete_account():
    """Deletes the current user's account."""
    user_to_delete = current_user._get_current_object()
    try:
        logout_user()
        security.datastore.delete_user(user_to_delete)
        db.session.commit()
        flash("Account deleted successfully.", "info")
        return redirect(url_for("core.index"))
    except Exception:  # noqa: BLE001
        db.session.rollback()
        flash("Unable to delete the account. Please try again later.", "error")
        return redirect(url_for("core.index"))


# ==================== SOS CONTACTS CRUD ====================

@auth_bp.route("/sos/contacts", methods=["GET"])
@auth_required()
def list_sos_contacts():
    """Lists all SOS contacts for the current user."""
    contacts = (
        SOSContact.query.filter_by(user_id=current_user.id)
        .order_by(SOSContact.priority.desc(), SOSContact.created_at.asc())
        .all()
    )
    return render_template("auth/sos_contacts_list.html", contacts=contacts)


@auth_bp.route("/sos/contacts/add", methods=["GET", "POST"])
@auth_required()
def add_sos_contact():
    """Adds a new SOS contact."""
    form = SOSContactForm()
    
    if form.validate_on_submit():
        # Check maximum contact limit (max 5)
        existing_count = SOSContact.query.filter_by(user_id=current_user.id).count()
        if existing_count >= 5:
            flash("You have reached the maximum number of SOS contacts (5). Remove an existing one to add a new one.", "error")
            return redirect(url_for("auth.list_sos_contacts"))
        
        contact = SOSContact(
            user_id=current_user.id,
            name=form.name.data.strip(),
            phone=form.phone.data.strip(),
            relationship=form.relationship.data if form.relationship.data else None,
            priority=int(form.priority.data)
        )
        db.session.add(contact)
        db.session.commit()
        
        flash(f"Contact '{contact.name}' added successfully!", "success")
        return redirect(url_for("auth.list_sos_contacts"))
    
    return render_template("auth/sos_contact_form.html", form=form, contact=None)


@auth_bp.route("/sos/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@auth_required()
def edit_sos_contact(contact_id):
    """Edits an existing SOS contact."""
    contact = SOSContact.query.filter_by(id=contact_id, user_id=current_user.id).first_or_404()
    
    form = SOSContactForm(obj=contact)
    
    if form.validate_on_submit():
        contact.name = form.name.data.strip()
        contact.phone = form.phone.data.strip()
        contact.relationship = form.relationship.data if form.relationship.data else None
        contact.priority = int(form.priority.data)
        db.session.commit()
        
        flash(f"Contact '{contact.name}' updated successfully!", "success")
        return redirect(url_for("auth.list_sos_contacts"))
    
    return render_template("auth/sos_contact_form.html", form=form, contact=contact)


@auth_bp.route("/sos/contacts/<int:contact_id>/delete", methods=["POST"])
@auth_required()
def delete_sos_contact(contact_id):
    """Deletes an SOS contact."""
    contact = SOSContact.query.filter_by(id=contact_id, user_id=current_user.id).first_or_404()
    
    contact_name = contact.name
    db.session.delete(contact)
    db.session.commit()
    
    flash(f"Contact '{contact_name}' deleted.", "info")
    return redirect(url_for("auth.list_sos_contacts"))


@auth_bp.route("/sos/contacts/reorder", methods=["POST"])
@auth_required()
def reorder_sos_contacts():
    """
    Reorders SOS contacts by updating priority.
    Expected JSON: {"contacts": [{"id": 1, "priority": 2}, ...]}
    """
    from flask import jsonify
    
    data = request.get_json()
    if not data or 'contacts' not in data:
        return jsonify({"error": "Invalid data"}), 400
    
    try:
        for item in data['contacts']:
            contact = SOSContact.query.filter_by(
                id=item['id'], 
                user_id=current_user.id
            ).first()
            if contact:
                contact.priority = int(item['priority'])
        
        db.session.commit()
        return jsonify({"status": "ok"}), 200
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
