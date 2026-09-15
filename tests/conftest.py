import logging

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.auth.models import user_datastore
from config import Config
from extensions import db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # Use in-memory SQLite for testing
    SQLALCHEMY_ENGINE_OPTIONS = {  # noqa: RUF012
        'poolclass': StaticPool,
        'connect_args': {'check_same_thread': False}
    }
    WTF_CSRF_ENABLED = False
    SECURITY_PASSWORD_HASH = 'plaintext'

@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test."""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        # Initialize test roles if needed
        if not user_datastore.find_role('admin'):
            user_datastore.create_role(name='admin', description='Admin Role')
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's cli commands."""
    return app.test_cli_runner()

@pytest.fixture(autouse=True)
def setup_logging(request):
    """Fixture to ensure logging happens for each test."""
    logger = logging.getLogger(request.node.name)
    
    # Recupera la descrizione iniziale del test (il suo docstring)
    description = request.node.function.__doc__
    if description:
        logger.info(f"Starting test: {request.node.name} - Descrizione: {description.strip()}")
    else:
        logger.info(f"Starting test: {request.node.name}")
        
    yield
    logger.info(f"Finished test: {request.node.name}")
