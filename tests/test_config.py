"""Tests for TimmyTest configuration loading."""

from pathlib import Path

from timmytest.config import TimmyConfig, load_project_config


def test_load_config_default(temp_project_dir: Path):
    cfg = load_project_config(temp_project_dir)
    assert isinstance(cfg, TimmyConfig)
    assert cfg.min_readiness_score == 0.0
    assert cfg.timeout_seconds == 60


def test_load_config_yaml(temp_project_dir: Path):
    yaml_content = """
min_readiness_score: 85.0
timeout_seconds: 45
ignored_dirs:
  - generated
  - fixtures
fail_on_test_failure: true
"""
    (temp_project_dir / ".timmytest.yml").write_text(yaml_content, encoding="utf-8")
    cfg = load_project_config(temp_project_dir)
    assert cfg.min_readiness_score == 85.0
    assert cfg.timeout_seconds == 45
    assert "generated" in cfg.ignored_dirs


def test_load_config_toml(temp_project_dir: Path):
    toml_content = """
min_readiness_score = 90.0
timeout_seconds = 120
custom_test_cmd = "uv run pytest"
"""
    (temp_project_dir / "timmytest.toml").write_text(toml_content, encoding="utf-8")
    cfg = load_project_config(temp_project_dir)
    assert cfg.min_readiness_score == 90.0
    assert cfg.timeout_seconds == 120
    assert cfg.custom_test_cmd == "uv run pytest"


def test_load_config_pyproject_toml(temp_project_dir: Path):
    pyproject_content = """
[project]
name = "sample-app"

[tool.timmytest]
min_readiness_score = 75.0
ignored_dirs = ["docs", "examples"]
"""
    (temp_project_dir / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")
    cfg = load_project_config(temp_project_dir)
    assert cfg.min_readiness_score == 75.0
    assert "docs" in cfg.ignored_dirs
