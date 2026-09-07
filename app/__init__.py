from flask import Flask

from config import Config
from extensions import csrf, db, migrate, security


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inizializza le estensioni
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Dobbiamo importare i datastore qui per evitare import circolari, ma i modelli vanno caricati.
    # L'import di user_datastore deve essere locale o fatto in modo attento.
    from app.auth.forms import ExtendedRegisterForm
    from app.auth.models import user_datastore
    security.init_app(app, user_datastore, register_form=ExtendedRegisterForm)

    # Registra i Blueprint
    from app.auth.routes import auth_bp
    from app.core.routes import core_bp
    from app.group import group_bp
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(group_bp)

    return app
