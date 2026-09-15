from flask import Flask

from config import Config
from extensions import csrf, db, migrate, security


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inizializza le estensioni
    db.init_app(app)
    migrate.init_app(app, db)
    from extensions import redis_client
    redis_client.connection_pool.connection_kwargs.update(
        host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT']
    )
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

    # Import telemetry models for migration detection
    from app.telemetry import models  # noqa: F401
    from app.telemetry.routes import telemetry_bp
    
    # Map feature
    from app.map import models as map_models  # noqa: F401
    from app.map.routes import pages_bp as map_pages_bp
    from app.map.api import api_bp as map_api_bp
    from app.map.osm_auth import osm_bp as map_osm_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(group_bp)
    app.register_blueprint(telemetry_bp, url_prefix='/telemetry')
    app.register_blueprint(map_pages_bp)
    app.register_blueprint(map_api_bp)
    app.register_blueprint(map_osm_bp)

    # Escludi le route OSM API da CSRF dato che autenticano tramite token/cookie PKCE
    csrf.exempt(map_osm_bp)


    return app
