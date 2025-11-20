"""Shared fixtures for integration tests."""

import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="function")
def setup_test_db():
    """Set up a unique test database for each integration test.

    Note: Not autouse to avoid interfering with unit tests that mock the database.
    Integration tests should explicitly use this fixture.
    """
    # Create unique temp database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    original_db_path = os.environ.get("PODX_DB_PATH")

    # Set env var
    os.environ["PODX_DB_PATH"] = db_path

    # Force reload of database module to pick up new path
    import sys

    # Remove cached modules
    modules_to_reload = [k for k in sys.modules if k.startswith("podx.server")]
    for module in modules_to_reload:
        del sys.modules[module]

    yield

    # Cleanup
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)

    # Restore original env var
    if original_db_path:
        os.environ["PODX_DB_PATH"] = original_db_path
    elif "PODX_DB_PATH" in os.environ:
        del os.environ["PODX_DB_PATH"]


@pytest.fixture(scope="function")
async def client(setup_test_db):
    """Create test client."""
    from podx.server.app import create_app
    from podx.server.database import init_db

    # Create the app
    app = create_app()

    # Manually initialize the database (lifespan doesn't run in tests)
    await init_db()

    # Create client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
