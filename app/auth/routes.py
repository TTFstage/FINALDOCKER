from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user, logout_user

from app.auth.forms import SOSContactForm
from app.auth.models import SOSContact, User, user_datastore
from extensions import db, security

auth_bp = Blueprint('auth', __name__)


@auth_bp.get("/me")
@auth_required()
def me():
    """Pagina del profilo utente con i contatti SOS."""
    # Ottieni i contatti SOS ordinati per priorità
    sos_contacts = (
        SOSContact.query.filter_by(user_id=current_user.id)
        .order_by(SOSContact.priority.desc(), SOSContact.created_at.asc())
        .all()
    )
    
    return render_template(
        "auth/private_page.html",
        username=current_user.username,
        phone_number=current_user.phone_number,
        email=current_user.email,
        sos_contacts=sos_contacts
    )


@auth_bp.post("/delete_account")
@auth_required()
def delete_account():
    """Elimina l'account dell'utente corrente."""
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
        return redirect(url_for("core.index"))


# ==================== SOS CONTACTS CRUD ====================

@auth_bp.route("/sos/contacts", methods=["GET"])
@auth_required()
def list_sos_contacts():
    """Lista tutti i contatti SOS dell'utente."""
    contacts = (
        SOSContact.query.filter_by(user_id=current_user.id)
        .order_by(SOSContact.priority.desc(), SOSContact.created_at.asc())
        .all()
    )
    return render_template("auth/sos_contacts_list.html", contacts=contacts)


@auth_bp.route("/sos/contacts/add", methods=["GET", "POST"])
@auth_required()
def add_sos_contact():
    """Aggiunge un nuovo contatto SOS."""
    form = SOSContactForm()
    
    if form.validate_on_submit():
        # Verifica limite massimo di contatti (es. max 5)
        existing_count = SOSContact.query.filter_by(user_id=current_user.id).count()
        if existing_count >= 5:
            flash("Hai raggiunto il numero massimo di contatti SOS (5). Rimuovi uno esistente per aggiungerne uno nuovo.", "error")
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
        
        flash(f"Contatto '{contact.name}' aggiunto con successo!", "success")
        return redirect(url_for("auth.list_sos_contacts"))
    
    return render_template("auth/sos_contact_form.html", form=form, contact=None)


@auth_bp.route("/sos/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@auth_required()
def edit_sos_contact(contact_id):
    """Modifica un contatto SOS esistente."""
    contact = SOSContact.query.filter_by(id=contact_id, user_id=current_user.id).first_or_404()
    
    form = SOSContactForm(obj=contact)
    
    if form.validate_on_submit():
        contact.name = form.name.data.strip()
        contact.phone = form.phone.data.strip()
        contact.relationship = form.relationship.data if form.relationship.data else None
        contact.priority = int(form.priority.data)
        db.session.commit()
        
        flash(f"Contatto '{contact.name}' aggiornato con successo!", "success")
        return redirect(url_for("auth.list_sos_contacts"))
    
    return render_template("auth/sos_contact_form.html", form=form, contact=contact)


@auth_bp.route("/sos/contacts/<int:contact_id>/delete", methods=["POST"])
@auth_required()
def delete_sos_contact(contact_id):
    """Elimina un contatto SOS."""
    contact = SOSContact.query.filter_by(id=contact_id, user_id=current_user.id).first_or_404()
    
    contact_name = contact.name
    db.session.delete(contact)
    db.session.commit()
    
    flash(f"Contatto '{contact_name}' eliminato.", "info")
    return redirect(url_for("auth.list_sos_contacts"))


@auth_bp.route("/sos/contacts/reorder", methods=["POST"])
@auth_required()
def reorder_sos_contacts():
    """
    Riordina i contatti SOS modificando la priorità.
    Atteso JSON: {\"contacts\": [{\"id\": 1, \"priority\": 2}, ...]}
    """
    from flask import jsonify
    
    data = request.get_json()
    if not data or 'contacts' not in data:
        return jsonify({"error": "Dati non validi"}), 400
    
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
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
