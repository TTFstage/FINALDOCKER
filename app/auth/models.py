import re
import secrets
import string
import uuid
from datetime import datetime, timezone

from flask_security import RoleMixin, SQLAlchemyUserDatastore, UserMixin
from sqlalchemy.orm import validates

from extensions import db

roles_users = db.Table('roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)    
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), default=True)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='selectin'))
    group_memberships = db.relationship('GroupMembership', back_populates='user', cascade='all, delete-orphan')

    # Validation to ensure that empty phone numbers are stored as NULL in the database
    @validates("phone_number")
    def validate_phone_number(self, key, value):
        if value is not None and not str(value).strip():
            return None  # Store NULL instead of empty string
        return value

class GroupMembership(db.Model):
    __tablename__ = 'group_memberships'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)
    
    role = db.Column(db.String(20), default='member', nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='group_memberships')
    group = db.relationship('Group', back_populates='members')

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    security_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    members = db.relationship('GroupMembership', back_populates='group', cascade='all, delete-orphan')

    @staticmethod
    def generate_group_code():
        """Genera un codice univoco per il gruppo (es. 'abc-defg-hij')."""
        part1 = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(3))
        part2 = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(4))
        part3 = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(3))
        return f"{part1}-{part2}-{part3}"

    @staticmethod
    def normalize_code(raw_code: str) -> str:
        """
        Normalizza il codice nel formato standard 'xxx-yyyy-zzz'.
        Supporta input con o senza trattini ed è insensibile alle maiuscole.
        """
        if not raw_code:
            return ""
        cleaned = re.sub(r'[^a-zA-Z]', '', raw_code).lower()
        if len(cleaned) == 10:
            return f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:]}"
        return raw_code.strip().lower()

    def generate_security_token(self):
        """Genera un nuovo token di sicurezza casuale url-safe."""
        self.security_token = secrets.token_urlsafe(32)
        return self.security_token

    def revoke_security_token(self):
        """Revoca il token di sicurezza attuale, invalidando i vecchi link di invito."""
        self.security_token = None

class RiderShift(db.Model):
    __tablename__ = 'rider_shifts'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    gpx_path = db.Column(db.String(512), nullable=False)
    total_distance_km = db.Column(db.Float, nullable=True)
    duration_min = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref=db.backref('rider_shifts', lazy=True))

class FallEvent(db.Model):
    __tablename__ = 'fall_events'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    user = db.relationship('User', backref=db.backref('fall_events', lazy=True))

# We initialize the user_datastore here, but we will pass it to security.init_app in the factory
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
