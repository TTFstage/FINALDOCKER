import logging

logger = logging.getLogger(__name__)

def test_index_page(client):
    """Test that the index page loads correctly."""
    logger.info("Testing the index route")
    response = client.get("/")
    assert response.status_code == 200
    # Add an assertion that matches the content of the index page if known
    assert True

def test_index_logging():
    """A simple test to demonstrate logging."""
    logger.info("This is a log message from the test_index_logging test.")
    assert True
