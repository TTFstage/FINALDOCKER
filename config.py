import os

from dotenv import load_dotenv

# Carica le variabili dal file .env nella directory corrente
load_dotenv()

class Config:
    # --- CHIAVI DI SICUREZZA ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chiave-fallback-da-non-usare-in-prod'
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or 'salt-fallback-da-non-usare-in-prod'

    # --- DATABASE CONFIGURATION ---
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'testlogin')

    # Costruzione sicura dell'URI SQLAlchemy usando psycopg (psycopg3)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 
        f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- FLASK-SECURITY CONFIGURATIONS ---
    SECURITY_REGISTERABLE = True
    SECURITY_SEND_REGISTER_EMAIL = False
    # Abilita la gestione nativa dell'username per login e registrazione
    # --- FLASK-SECURITY CONFIGURATIONS ---
    SECURITY_POST_LOGIN_VIEW = '/me'
    SECURITY_USERNAME_ENABLE = True
    SECURITY_USERNAME_REQUIRED = True
    SECURITY_USER_IDENTITY_ATTRIBUTES = [  # noqa: RUF012
            {"email": {"case_insensitive": True}},
            {"username": {"case_insensitive": True}}
        ]
    SECURITY_PASSWORD_HASH = 'bcrypt' # Tipo di hashing consigliato

    # --- SICUREZZA COOKIE E SESSIONI (HARDENING) ---
    # Impedisce a JavaScript di leggere i cookie di sessione (Protezione contro attacchi XSS)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Previene l'invio dei cookie in contesti cross-site (Protezione contro attacchi CSRF)
    SESSION_COOKIE_SAMESITE = 'Lax' # Opzioni: 'Strict', 'Lax', 'None' (se si usa 'None', assicurarsi di usare HTTPS)
    
    # Abilita la protezione CSRF su tutti i form WTForms
    WTF_CSRF_ENABLED = True

    # NOTA PER LA PRODUZIONE (quando si usa HTTPS):
    # SESSION_COOKIE_SECURE = True
    # REMEMBER_COOKIE_SECURE = True
    