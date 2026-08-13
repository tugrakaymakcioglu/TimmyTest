"""Test configuration and shared fixtures for TimmyTest."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_project_dir():
    """Provides a temporary directory for creating dummy projects."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)
