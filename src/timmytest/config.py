"""Configuration loader for TimmyTest.

Supports .timmytest.yml, .timmytest.yaml, timmytest.toml, and pyproject.toml [tool.timmytest].
"""

import tomllib
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class TimmyConfig(BaseModel):
    """TimmyTest user configuration."""

    ignored_dirs: list[str] = Field(default_factory=list)
    ignored_files: list[str] = Field(default_factory=list)
    min_readiness_score: float = 0.0
    timeout_seconds: int = 60
    custom_test_cmd: str | None = None
    fail_on_test_failure: bool = True
    copy_prompt: bool = True
    watch_interval: float = 1.0


def load_project_config(root_dir: Path) -> TimmyConfig:
    """
    Attempts to load TimmyTest configuration from root directory files in priority order:
    1. .timmytest.yml / .timmytest.yaml
    2. timmytest.toml
    3. pyproject.toml under [tool.timmytest]
    """
    root = root_dir.resolve()

    # 1. Check YAML config
    for yml_name in [".timmytest.yml", ".timmytest.yaml", "timmytest.yml", "timmytest.yaml"]:
        yml_path = root / yml_name
        if yml_path.is_file():
            try:
                data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return TimmyConfig(**data)
            except Exception:
                pass

    # 2. Check timmytest.toml
    toml_path = root / "timmytest.toml"
    if toml_path.is_file():
        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return TimmyConfig(**data)
        except Exception:
            pass

    # 3. Check pyproject.toml [tool.timmytest]
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.is_file():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tool" in data and "timmytest" in data["tool"]:
                tool_cfg = data["tool"]["timmytest"]
                if isinstance(tool_cfg, dict):
                    return TimmyConfig(**tool_cfg)
        except Exception:
            pass

    return TimmyConfig()
