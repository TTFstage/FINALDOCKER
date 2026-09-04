from flask import flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.auth.models import Group, GroupMembership
from app.group import group_bp
from extensions import db


@group_bp.route('/', methods=['GET'])
@auth_required()
def index():
    """Elenco dei gruppi di cui l'utente corrente fa parte."""
    memberships = (
        GroupMembership.query.filter_by(user_id=current_user.id)
        .join(Group)
        .order_by(GroupMembership.joined_at.desc())
        .all()
    )
    return render_template('group/index.html', memberships=memberships)


@group_bp.route('/create', methods=['GET', 'POST'])
@auth_required()
def create():
    """Creazione di un nuovo gruppo."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash("Il nome del gruppo è obbligatorio.", "error")
            return render_template('group/create.html', name=name, description=description)

        # Genera un codice univoco (xxx-yyyy-zzz)
        code = Group.generate_group_code()
        while Group.query.filter_by(code=code).first() is not None:
            code = Group.generate_group_code()

        new_group = Group(
            name=name,
            description=description or None,
            code=code
        )
        # Genera il token di sicurezza iniziale per i link d'invito
        new_group.generate_security_token()

        db.session.add(new_group)
        db.session.flush()  # Popola new_group.id

        # Assegna l'utente corrente come owner del gruppo
        membership = GroupMembership(
            user_id=current_user.id,
            group_id=new_group.id,
            role='owner'
        )
        db.session.add(membership)
        db.session.commit()

        flash(f"Gruppo '{new_group.name}' creato con successo!", "success")
        return redirect(url_for('group.detail', group_id=new_group.id))

    return render_template('group/create.html')


@group_bp.route('/<int:group_id>', methods=['GET'])
@auth_required()
def detail(group_id):
    """Scheda di dettaglio del gruppo, membri e gestione inviti."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership:
        flash("Non fai parte di questo gruppo.", "error")
        return redirect(url_for('group.index'))

    invite_url = None
    if group.security_token:
        invite_url = url_for('group.join_by_token', token=group.security_token, _external=True)

    members = (
        GroupMembership.query.filter_by(group_id=group.id)
        .order_by(GroupMembership.joined_at.asc())
        .all()
    )

    return render_template(
        'group/detail.html',
        group=group,
        membership=membership,
        members=members,
        invite_url=invite_url
    )


@group_bp.route('/<int:group_id>/token/generate', methods=['POST'])
@auth_required()
def generate_token(group_id):
    """Genera o rigenera un token di sicurezza per il gruppo (invito via link)."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("Non hai i permessi per eseguire questa operazione.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    group.generate_security_token()
    db.session.commit()

    flash("Nuovo link di invito generato con successo!", "success")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/token/revoke', methods=['POST'])
@auth_required()
def revoke_token(group_id):
    """Revoca il token di sicurezza, disabilitando i link d'invito attivi."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("Non hai i permessi per eseguire questa operazione.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    group.revoke_security_token()
    db.session.commit()

    flash("Link di invito revocato con successo. I vecchi link non sono più validi.", "info")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/code/generate', methods=['POST'])
@auth_required()
def generate_code(group_id):
    """Rigenera il codice del gruppo."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("Non hai i permessi per eseguire questa operazione.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    # Genera un nuovo codice univoco
    new_code = Group.generate_group_code()
    while Group.query.filter_by(code=new_code).first() is not None:
        new_code = Group.generate_group_code()

    group.code = new_code
    db.session.commit()

    flash("Nuovo codice gruppo generato con successo! Il vecchio codice non è più valido.", "success")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/member/<int:user_id>/role', methods=['POST'])
@auth_required()
def change_role(group_id, user_id):
    """Cambia il ruolo di un membro (solo l'owner può farlo)."""
    group = Group.query.get_or_404(group_id)

    # Verifica che l'utente corrente sia l'owner
    current_membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not current_membership or current_membership.role != 'owner':
        flash("Solo l'owner del gruppo può modificare i ruoli.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    # Impedisci all'owner di modificare se stesso
    if current_user.id == user_id:
        flash("Non puoi modificare il tuo stesso ruolo.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    target_membership = GroupMembership.query.filter_by(
        user_id=user_id, group_id=group.id
    ).first_or_404()

    new_role = request.form.get('role')
    if new_role not in ['admin', 'member']:
        flash("Ruolo non valido.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    target_membership.role = new_role
    db.session.commit()

    flash(f"Ruolo di {target_membership.user.username} aggiornato a {new_role}.", "success")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/join', methods=['GET', 'POST'])
@auth_required()
def join():
    """Inserimento manuale del codice univoco (es. abc-defg-hij)."""
    if request.method == 'POST':
        raw_code = request.form.get('code', '').strip()
        if not raw_code:
            flash("Inserisci un codice di gruppo valido.", "error")
            return render_template('group/join.html')

        normalized_code = Group.normalize_code(raw_code)

        # Cerca per codice formattato o codice originale minuscolo
        group = Group.query.filter(
            (Group.code == normalized_code) | (Group.code == raw_code.lower())
        ).first()

        if not group:
            flash("Nessun gruppo trovato con il codice specificato. Verifica e riprova.", "error")
            return render_template('group/join.html', entered_code=raw_code)

        existing_membership = GroupMembership.query.filter_by(
            user_id=current_user.id, group_id=group.id
        ).first()

        if existing_membership:
            flash(f"Fai già parte del gruppo '{group.name}'.", "info")
            return redirect(url_for('group.detail', group_id=group.id))

        new_membership = GroupMembership(
            user_id=current_user.id,
            group_id=group.id,
            role='member'
        )
        db.session.add(new_membership)
        db.session.commit()

        flash(f"Ti sei unito con successo al gruppo '{group.name}'!", "success")
        return redirect(url_for('group.detail', group_id=group.id))

    return render_template('group/join.html')


@group_bp.route('/join/<string:token>', methods=['GET', 'POST'])
@auth_required()
def join_by_token(token):
    """Accesso al gruppo tramite link d'invito con token di sicurezza."""
    group = Group.query.filter_by(security_token=token).first()

    if not group or not group.security_token:
        flash("Link di invito non valido o revocato.", "error")
        return redirect(url_for('group.index'))

    existing_membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if existing_membership:
        flash(f"Fai già parte del gruppo '{group.name}'.", "info")
        return redirect(url_for('group.detail', group_id=group.id))

    if request.method == 'POST':
        new_membership = GroupMembership(
            user_id=current_user.id,
            group_id=group.id,
            role='member'
        )
        db.session.add(new_membership)
        db.session.commit()

        flash(f"Ti sei unito con successo al gruppo '{group.name}'!", "success")
        return redirect(url_for('group.detail', group_id=group.id))

    return render_template('group/join_invite.html', group=group, token=token)
