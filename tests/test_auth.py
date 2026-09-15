import logging

from app.auth.models import user_datastore
from extensions import db

logger = logging.getLogger(__name__)

def test_user_creation(app):
    """Test that a user can be created via the datastore."""
    logger.info("Testing user creation")
    with app.app_context():
        user_datastore.create_user(
            email="test@example.com",
            password="password",
            username="testuser"
        )
        db.session.commit()
        
        fetched_user = user_datastore.find_user(email="test@example.com")
        assert fetched_user is not None
        assert fetched_user.username == "testuser"

def test_login_page_loads(client):
    """Test that the login page loads."""
    logger.info("Testing login page load")
    response = client.get("/login") # Flask-Security defaults
    assert response.status_code == 200
