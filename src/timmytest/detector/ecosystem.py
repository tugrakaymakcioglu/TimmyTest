"""Ecosystem and test runner detection engine.

Detection logic lives in the data-driven registry (``registry/ecosystems.yaml``)
rather than hardcoded ``if``/``else`` blocks. This module wraps
``timmytest.registry.loader.detect_from_registry`` and converts its raw string
ids into the ``Ecosystem`` / ``TestFramework`` enums, so that adding a language
requires editing YAML only, not this file.
"""

from pathlib import Path

from timmytest.detector.models import Ecosystem, TestFramework
from timmytest.registry.loader import detect_from_registry


def _to_ecosystem(eco_id: str) -> Ecosystem:
    try:
        return Ecosystem(eco_id)
    except ValueError:
        return Ecosystem.UNKNOWN


def _to_framework(fw_id: str) -> TestFramework:
    try:
        return TestFramework(fw_id)
    except ValueError:
        return TestFramework.UNKNOWN


def detect_ecosystem(root_path: Path) -> tuple[Ecosystem, TestFramework, str, list[str]]:
    """
    Detects the primary ecosystem, test framework, recommended test command,
    and detected configuration files for a given directory.

    Returns:
        (Ecosystem, TestFramework, test_command, config_files)
    """
    eco_id, fw_id, command, configs = detect_from_registry(Path(root_path))
    return _to_ecosystem(eco_id), _to_framework(fw_id), command, configs
