"""
Shabd.Craft — Pytest Configuration & Test Fixtures
Ensures test suite runs in isolated offline/deterministic mode.
"""

import os
import pytest
from src.config import settings


@pytest.fixture(autouse=True)
def isolated_test_environment(monkeypatch):
    """Enforce deterministic demo mode during test runs regardless of local .env."""
    monkeypatch.setenv("SHABDCRAFT_DEMO_MODE", "true")
    settings._reload()
    yield
    settings._reload()
