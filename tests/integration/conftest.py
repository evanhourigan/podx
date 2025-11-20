"""Shared fixtures for integration tests."""

import os

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="function")
def setup_test_db():
    """Set up a unique test database for each integration test.

    Uses in-memory SQLite database for all platforms to ensure:
    - Fast test execution
    - No file locking issues (especially on Windows)
    - Clean isolation between tests
    - No cleanup required

    Note: Not autouse to avoid interfering with unit tests that mock the database.
    Integration tests should explicitly use this fixture.
    """
    # Use in-memory database for all tests
    original_db_path = os.environ.get("PODX_DB_PATH")

    # Set to in-memory database
    os.environ["PODX_DB_PATH"] = ":memory:"

    # Force reload of database module to pick up new path
    import sys

    # Remove cached modules
    modules_to_reload = [k for k in sys.modules if k.startswith("podx.server")]
    for module in modules_to_reload:
        del sys.modules[module]

    yield

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
