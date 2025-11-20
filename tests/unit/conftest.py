"""Shared fixtures for unit tests."""

import sys

import pytest


@pytest.fixture(autouse=True)
def reset_server_state():
    """Reset server module state between tests to prevent test pollution.

    This fixture ensures that global state in server modules (like
    _SERVER_START_TIME in health.py) is properly isolated between tests.
    """
    # Store original upload directory state
    original_modules = {}
    server_modules = [k for k in sys.modules if k.startswith("podx.server")]

    for module_name in server_modules:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            # Save module state if it has important globals
            if hasattr(module, "_SERVER_START_TIME"):
                original_modules[module_name] = {
                    "_SERVER_START_TIME": getattr(module, "_SERVER_START_TIME", None)
                }

    yield

    # Restore original state
    for module_name, state in original_modules.items():
        if module_name in sys.modules:
            module = sys.modules[module_name]
            for attr, value in state.items():
                setattr(module, attr, value)


@pytest.fixture
def temp_upload_dir(tmp_path):
    """Provide a temporary upload directory for tests.

    This prevents tests from using the real ~/.podx/uploads directory.
    """
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir
