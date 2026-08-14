"""Runtime feature switches for TimmyTest.

TimmyTest only ever *reads* switches - it has no code that writes one. That is
deliberate: an install can be steered by a config file its owner controls, but
nothing inside the shipped package can flip a switch on its own.

Resolution order (first file that parses wins):

1. ``$TIMMYTEST_FLAGS``            - explicit path, useful in CI
2. ``./.timmytest-features.json``  - per-project override, commit it with the repo
3. ``$TIMMYTEST_HOME/features.json`` (default ``~/.timmytest/features.json``)

File format - both keys are optional::

    {
      "features": {"cli.mcp": false, "tui.discord_send": true},
      "disabled": ["tui.discord_webhook"]
    }

Anything not mentioned is enabled. Every failure mode - missing file, bad JSON,
unreadable directory - resolves to "enabled", because a broken switch file must
never be able to take the tool offline.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

FLAGS_FILENAME = "features.json"
PROJECT_FLAGS_FILENAME = ".timmytest-features.json"

# Command switches. Keys mirror the CLI command names.
CLI_FEATURES: tuple[str, ...] = (
    "cli.check",
    "cli.scan",
    "cli.run",
    "cli.prompt",
    "cli.init",
    "cli.integrate",
    "cli.agent",
    "cli.ui",
    "cli.mcp",
)

# Engine switches that are not tied to a single command.
CORE_FEATURES: tuple[str, ...] = (
    "core.registry_learning",
    "core.coverage",
    "core.watch",
    "core.clipboard",
)


def app_dir() -> Path:
    """The TimmyTest home directory (kept in sync with ``tui.state.APP_DIR``)."""
    return Path(os.environ.get("TIMMYTEST_HOME", Path.home() / ".timmytest"))


def candidate_paths() -> list[Path]:
    """Every location that is consulted, in priority order."""
    paths: list[Path] = []
    explicit = os.environ.get("TIMMYTEST_FLAGS")
    if explicit:
        paths.append(Path(explicit))
    # cwd can be gone if the directory was deleted underneath us.
    with contextlib.suppress(OSError):
        paths.append(Path.cwd() / PROJECT_FLAGS_FILENAME)
    paths.append(app_dir() / FLAGS_FILENAME)
    return paths


def _parse(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    resolved: dict[str, bool] = {}
    features = raw.get("features")
    if isinstance(features, dict):
        for key, value in features.items():
            if isinstance(key, str):
                resolved[key] = bool(value)
    disabled = raw.get("disabled")
    if isinstance(disabled, list):
        for key in disabled:
            if isinstance(key, str):
                resolved[key] = False
    return resolved


def _load() -> tuple[dict[str, bool], Path | None]:
    for path in candidate_paths():
        try:
            if not path.is_file():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return _parse(raw), path
    return {}, None


_cache: tuple[dict[str, bool], Path | None] | None = None


def refresh() -> None:
    """Drop the cached switch file; the next lookup re-reads from disk."""
    global _cache
    _cache = None


def _state() -> tuple[dict[str, bool], Path | None]:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def source_path() -> Path | None:
    """Which file the active switches came from, or ``None`` for defaults."""
    return _state()[1]


def overrides() -> dict[str, bool]:
    """The raw switch map as loaded from disk (a copy; edits do not stick)."""
    return dict(_state()[0])


def is_enabled(key: str, default: bool = True) -> bool:
    """Whether ``key`` is switched on. Unknown keys keep ``default``."""
    return _state()[0].get(key, default)


def disabled_keys() -> tuple[str, ...]:
    """Every key that is explicitly switched off."""
    return tuple(sorted(k for k, v in _state()[0].items() if not v))
