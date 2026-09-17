import os

from dotenv import load_dotenv

# Load environment variables from .env file in the current directory
load_dotenv()

class Config:
    # --- SECURITY KEYS ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-key-do-not-use-in-prod'
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or 'fallback-salt-do-not-use-in-prod'

    # --- DATABASE CONFIGURATION ---
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'testlogin')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))

    # Safe retrieval and construction of the SQLAlchemy URI using psycopg (psycopg3)
    _raw_db_url = os.environ.get('DATABASE_URL')
    if _raw_db_url:
        if _raw_db_url.startswith('postgres://'):
            _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif _raw_db_url.startswith('postgresql://') and not _raw_db_url.startswith('postgresql+'):
            _raw_db_url = _raw_db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        SQLALCHEMY_DATABASE_URI = _raw_db_url
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- FLASK-SECURITY CONFIGURATIONS ---
    SECURITY_REGISTERABLE = True
    SECURITY_SEND_REGISTER_EMAIL = False
    # Enable native username management for login and registration
    # --- FLASK-SECURITY CONFIGURATIONS ---
    SECURITY_POST_LOGIN_VIEW = '/me'
    SECURITY_USERNAME_ENABLE = True
    SECURITY_USERNAME_REQUIRED = True
    SECURITY_USER_IDENTITY_ATTRIBUTES = [  # noqa: RUF012
            {"email": {"case_insensitive": True}},
            {"username": {"case_insensitive": True}}
        ]
    SECURITY_PASSWORD_HASH = 'bcrypt'  # Recommended hashing type

    # --- COOKIE AND SESSION SECURITY (HARDENING) ---
    # Prevents JavaScript from reading session cookies (protection against XSS attacks)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Prevents cookies from being sent in cross-site contexts (protection against CSRF attacks)
    SESSION_COOKIE_SAMESITE = 'Lax'  # Options: 'Strict', 'Lax', 'None' (if using 'None', ensure HTTPS is used)
    
    # Enables CSRF protection on all WTForms forms
    WTF_CSRF_ENABLED = True

    # NOTE FOR PRODUCTION (when using HTTPS):
    # SESSION_COOKIE_SECURE = True
    # REMEMBER_COOKIE_SECURE = True
