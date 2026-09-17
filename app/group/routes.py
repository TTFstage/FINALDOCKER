import json

from flask import abort, flash, jsonify, redirect, render_template, url_for
from flask_security import auth_required, current_user

from app.auth.models import Group, GroupMembership
from app.group import group_bp
from app.group.forms import (
    ChangeRoleForm,
    CreateGroupForm,
    JoinByTokenForm,
    JoinGroupForm,
)
from extensions import db, redis_client


def normalize_code(code: str) -> str:
    """Normalizes a group code by removing spaces and dashes."""
    return code.replace('-', '').replace(' ', '').lower()


@group_bp.route('/', methods=['GET'])
@auth_required()
def index():
    """List of groups the current user belongs to."""
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
    """Create a new group."""
    form = CreateGroupForm()

    if form.validate_on_submit():
        # Generate a unique code (xxx-yyyy-zzz)
        code = Group.generate_group_code()
        while Group.query.filter_by(code=code).first() is not None:
            code = Group.generate_group_code()

        new_group = Group(
            name=form.name.data.strip(),
            description=form.description.data.strip() or None,
            code=code
        )
        # Generate the initial security token for invite links
        new_group.generate_security_token()

        db.session.add(new_group)
        db.session.flush()  # Populate new_group.id

        # Assign the current user as the group owner
        membership = GroupMembership(
            user_id=current_user.id,
            group_id=new_group.id,
            role='owner'
        )
        db.session.add(membership)
        db.session.commit()

        flash(f"Group '{new_group.name}' created successfully!", "success")
        return redirect(url_for('group.detail', group_id=new_group.id))

    # GET request or failed validation
    return render_template(
        'group/create.html',
        form=form,
        name=form.name.data or '',
        description=form.description.data or ''
    )


@group_bp.route('/<int:group_id>', methods=['GET'])
@auth_required()
def detail(group_id):
    """Group detail page with members and invite management."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership:
        flash("You are not a member of this group.", "error")
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
    """Generates or regenerates a security token for the group (invite via link)."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("You do not have permission to perform this operation.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    group.generate_security_token()
    db.session.commit()

    flash("New invite link generated successfully!", "success")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/token/revoke', methods=['POST'])
@auth_required()
def revoke_token(group_id):
    """Revokes the security token, disabling active invite links."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("You do not have permission to perform this operation.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    group.revoke_security_token()
    db.session.commit()

    flash("Invite link revoked successfully. Old links are no longer valid.", "info")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/code/generate', methods=['POST'])
@auth_required()
def generate_code(group_id):
    """Regenerates the group code."""
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash("You do not have permission to perform this operation.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    # Generate a new unique code
    new_code = Group.generate_group_code()
    while Group.query.filter_by(code=new_code).first() is not None:
        new_code = Group.generate_group_code()

    group.code = new_code
    db.session.commit()

    flash("New group code generated successfully! The old code is no longer valid.", "success")
    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/<int:group_id>/member/<int:user_id>/role', methods=['POST'])
@auth_required()
def change_role(group_id, user_id):
    """Changes a member's role (only the owner can do this)."""
    group = Group.query.get_or_404(group_id)

    # Verify that the current user is the owner
    current_membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if not current_membership or current_membership.role != 'owner':
        flash("Only the group owner can modify roles.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    # Prevent the owner from modifying themselves
    if current_user.id == user_id:
        flash("You cannot change your own role.", "error")
        return redirect(url_for('group.detail', group_id=group.id))

    target_membership = GroupMembership.query.filter_by(
        user_id=user_id, group_id=group.id
    ).first_or_404()

    form = ChangeRoleForm()

    if form.validate_on_submit():
        target_membership.role = form.role.data
        db.session.commit()
        flash(f"Role of {target_membership.user.username} updated to {form.role.data}.", "success")
    else:
        flash("Invalid role.", "error")

    return redirect(url_for('group.detail', group_id=group.id))


@group_bp.route('/join', methods=['GET', 'POST'])
@auth_required()
def join():
    """Manual entry of the unique code (e.g. abc-defg-hij)."""
    form = JoinGroupForm()

    if form.validate_on_submit():
        normalized_code = normalize_code(form.code.data)

        # Search by normalized code
        group = Group.query.filter(
            (Group.code == normalized_code) | 
            (Group.code == form.code.data.lower())
        ).first()

        if not group:
            flash("No group found with the specified code. Please check and try again.", "error")
            return render_template('group/join.html', form=form, entered_code=form.code.data)

        existing_membership = GroupMembership.query.filter_by(
            user_id=current_user.id, group_id=group.id
        ).first()

        if existing_membership:
            flash(f"You are already a member of group '{group.name}'.", "info")
            return redirect(url_for('group.detail', group_id=group.id))

        new_membership = GroupMembership(
            user_id=current_user.id,
            group_id=group.id,
            role='member'
        )
        db.session.add(new_membership)
        db.session.commit()

        flash(f"You have successfully joined the group '{group.name}'!", "success")
        return redirect(url_for('group.detail', group_id=group.id))

    # GET request or failed validation
    return render_template('group/join.html', form=form, entered_code=form.code.data if form.code.data else '')


@group_bp.route('/join/<string:token>', methods=['GET', 'POST'])
@auth_required()
def join_by_token(token):
    """Access to a group via invite link with security token."""
    group = Group.query.filter_by(security_token=token).first()

    if not group or not group.security_token:
        flash("Invalid or revoked invite link.", "error")
        return redirect(url_for('group.index'))

    existing_membership = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group.id
    ).first()

    if existing_membership:
        flash(f"You are already a member of group '{group.name}'.", "info")
        return redirect(url_for('group.detail', group_id=group.id))

    form = JoinByTokenForm()

    if form.validate_on_submit():
        new_membership = GroupMembership(
            user_id=current_user.id,
            group_id=group.id,
            role='member'
        )
        db.session.add(new_membership)
        db.session.commit()

        flash(f"You have successfully joined the group '{group.name}'!", "success")
        return redirect(url_for('group.detail', group_id=group.id))

    return render_template('group/join_invite.html', group=group, token=token, form=form)


@group_bp.route('/<int:group_id>/member/<int:user_id>/position', methods=['GET'])
@auth_required()
def member_position(group_id, user_id):
    requester = GroupMembership.query.filter_by(
        user_id=current_user.id, group_id=group_id
    ).first()
    target = GroupMembership.query.filter_by(
        user_id=user_id, group_id=group_id
    ).first()

    if not requester or not target:
        abort(403)

    # user_id = user_id (solution 1): the Redis key matches
    data = redis_client.get(f"position:{user_id}")
    if not data:
        return jsonify({"available": False})

    return jsonify({"available": True, **json.loads(data)})
