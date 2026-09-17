from flask import Flask

from config import Config
from extensions import csrf, db, migrate, security


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    from extensions import redis_client
    redis_client.connection_pool.connection_kwargs.update(
        host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT']
    )
    csrf.init_app(app)
    
    # We must import the datastores here to avoid circular imports, but models need to be loaded.
    # The import of user_datastore must be local or done carefully.
    from app.auth.forms import ExtendedRegisterForm
    from app.auth.models import user_datastore
    security.init_app(app, user_datastore, register_form=ExtendedRegisterForm)

    # Register Blueprints
    # Analytics feature
    from app.analytics import analytics_bp
    from app.auth.routes import auth_bp
    from app.core.routes import core_bp
    from app.group import group_bp

    # Map feature
    from app.map import models as map_models  # noqa: F401
    from app.map.api import api_bp as map_api_bp
    from app.map.routes import pages_bp as map_pages_bp

    # Import telemetry models for migration detection
    from app.telemetry import models  # noqa: F401
    from app.telemetry.routes import telemetry_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(group_bp)
    app.register_blueprint(telemetry_bp, url_prefix='/telemetry')
    app.register_blueprint(map_pages_bp)
    app.register_blueprint(map_api_bp)
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    # Other hub
    from app.other import other_bp
    app.register_blueprint(other_bp, url_prefix='/other')

    return app
