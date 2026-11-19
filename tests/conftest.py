"""
Shabd.Craft — Pytest Configuration & Test Fixtures
Ensures test suite runs in isolated offline/deterministic mode.
"""

import pytest
from src.config import clear_current_settings, settings


@pytest.fixture(autouse=True)
def isolated_test_environment(monkeypatch, tmp_path):
    """Keep tests offline and prevent app tests from touching the user database."""
    with monkeypatch.context() as patch:
        patch.setenv("SHABDCRAFT_DEMO_MODE", "true")
        patch.setenv("SHABDCRAFT_DB_PATH", str(tmp_path / "shabdcraft-test.db"))
        settings._reload()
        yield
    # Restore the base settings after pytest restores env vars.
    clear_current_settings()
    settings._reload()


@pytest.fixture
def test_db_path(tmp_path):
    """Return a fresh database path for tests that exercise database selection."""
    return tmp_path / "workspace.db"
