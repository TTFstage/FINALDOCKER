import logging
import os
import subprocess
import sys
import time
import urllib.request

import pytest

logger = logging.getLogger(__name__)

def test_waitress_server_starts():
    """Test that the application can be served using Waitress via wsgi.py."""
    logger.info("Starting Waitress subprocess for testing...")
    
    # Ensure FLASK_DEBUG is not set so that waitress is triggered
    env = os.environ.copy()
    env["FLASK_DEBUG"] = "False"
    # Set testing env vars for safety so it doesn't connect to production DB
    env["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    # Get path to python executable in the virtualenv
    python_exe = sys.executable

    # Start wsgi.py as a subprocess
    process = subprocess.Popen(
        [python_exe, "wsgi.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Allow some time for the server to bind to port 8080
    time.sleep(2)
    
    # Verify process is still running and hasn't crashed
    if process.poll() is not None:
        _, stderr = process.communicate()
        logger.error(f"Waitress server crashed immediately. Stderr: {stderr.decode()}")
        pytest.fail("Waitress server failed to start.")

    success = False
    try:
        logger.info("Attempting to connect to Waitress on http://localhost:8080/")
        response = urllib.request.urlopen("http://localhost:8080/", timeout=5)
        # 200 OK means it's serving requests
        assert response.status == 200
        success = True
        logger.info("Successfully connected to Waitress server.")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to connect to Waitress: {e}")
    finally:
        # Stop the subprocess
        logger.info("Terminating Waitress subprocess.")
        process.terminate()
        process.wait(timeout=5)
        
    assert success, "Could not fetch a response from the Waitress server."
