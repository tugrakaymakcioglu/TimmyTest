"""System requirement and file integrity checks shown on the setup screen."""

from __future__ import annotations

import importlib
import locale
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from timmytest import __version__
from timmytest.tui.state import APP_DIR

MIN_PYTHON = (3, 11)
MIN_COLUMNS = 90
MIN_ROWS = 26

# Every module the application refuses to start without.
REQUIRED_MODULES = [
    "timmytest.analysis",
    "timmytest.config",
    "timmytest.detector.scanner",
    "timmytest.detector.gap_analyzer",
    "timmytest.diagnostics.analyzer",
    "timmytest.integrations.installer",
    "timmytest.mcp.server",
    "timmytest.prompt.generator",
    "timmytest.reports.markdown",
    "timmytest.runner.orchestrator",
    "timmytest.scaffolder.init_tests",
    "timmytest.tui.pixelart",
]


class Level(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    key: str
    label: str
    level: Level
    detail: str


@dataclass
class Check:
    key: str
    label: str
    run: Callable[[], tuple[Level, str]]

    def execute(self) -> CheckResult:
        try:
            level, detail = self.run()
        except Exception as exc:  # a broken check must never kill the setup screen
            level, detail = Level.FAIL, f"{type(exc).__name__}: {exc}"
        return CheckResult(self.key, self.label, level, detail)


# --------------------------------------------------------------------------- #
# System requirements
# --------------------------------------------------------------------------- #


def _check_python() -> tuple[Level, str]:
    version = ".".join(str(p) for p in sys.version_info[:3])
    if sys.version_info[:2] < MIN_PYTHON:
        return Level.FAIL, f"{version} < {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return Level.OK, f"Python {version}"


def _check_terminal_size(size: tuple[int, int] | None = None) -> tuple[Level, str]:
    if size is None:
        fallback = shutil.get_terminal_size((80, 24))
        size = (fallback.columns, fallback.lines)
    columns, rows = size
    detail = f"{columns}x{rows}"
    if columns < MIN_COLUMNS or rows < MIN_ROWS:
        return Level.WARN, f"{detail} (min {MIN_COLUMNS}x{MIN_ROWS})"
    return Level.OK, detail


def _check_truecolor() -> tuple[Level, str]:
    colorterm = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in colorterm or "24bit" in colorterm:
        return Level.OK, "24-bit"
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"):
        return Level.OK, "24-bit"
    if sys.platform == "win32":
        return Level.OK, "24-bit (Windows console)"
    if os.environ.get("TERM", "").endswith("256color"):
        return Level.WARN, "256 colours only"
    return Level.WARN, "unknown"


def _check_encoding() -> tuple[Level, str]:
    # While the app runs, ``sys.stdout`` is Textual's redirector, which carries no
    # encoding of its own - the real console is ``sys.__stdout__``.
    for stream in (sys.__stdout__, sys.stdout):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding:
            return (Level.OK if "utf" in encoding else Level.WARN), encoding
    return Level.WARN, locale.getpreferredencoding(False).lower() or "unknown"


def _check_writable_home() -> tuple[Level, str]:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        probe = APP_DIR / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Level.FAIL, f"{APP_DIR}: {exc.strerror or exc}"
    return Level.OK, str(APP_DIR)


def _check_disk() -> tuple[Level, str]:
    try:
        usage = shutil.disk_usage(APP_DIR if APP_DIR.exists() else Path.home())
    except OSError as exc:
        return Level.WARN, str(exc)
    free_mb = usage.free / (1024 * 1024)
    if free_mb < 64:
        return Level.WARN, f"{free_mb:.0f} MB free"
    return Level.OK, f"{free_mb / 1024:.1f} GB free"


def _check_cpu() -> tuple[Level, str]:
    cores = os.cpu_count() or 1
    return (Level.OK if cores >= 2 else Level.WARN), f"{cores} logical cores"


def _check_git() -> tuple[Level, str]:
    git = shutil.which("git")
    if git:
        return Level.OK, git
    return Level.WARN, "not found (optional)"


def system_checks(terminal_size: tuple[int, int] | None = None) -> list[Check]:
    """System requirement checks; ``terminal_size`` overrides the detected size."""
    return [
        Check("python", "Python runtime", _check_python),
        Check("terminal", "Terminal size", lambda: _check_terminal_size(terminal_size)),
        Check("color", "TrueColor support", _check_truecolor),
        Check("encoding", "UTF-8 output", _check_encoding),
        Check("home", "Config directory", _check_writable_home),
        Check("disk", "Free disk space", _check_disk),
        Check("cpu", "CPU cores", _check_cpu),
        Check("git", "Git executable", _check_git),
    ]


# --------------------------------------------------------------------------- #
# File integrity
# --------------------------------------------------------------------------- #


def _check_modules() -> tuple[Level, str]:
    missing = []
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name.rsplit(".", 1)[-1])
    if missing:
        return Level.FAIL, "missing: " + ", ".join(missing)
    return Level.OK, f"{len(REQUIRED_MODULES)} modules verified"


def _check_package_tree() -> tuple[Level, str]:
    import timmytest

    root = Path(timmytest.__file__).parent
    files = list(root.rglob("*.py"))
    if len(files) < 20:
        return Level.FAIL, f"only {len(files)} modules found in {root}"
    total_kb = sum(f.stat().st_size for f in files) / 1024
    return Level.OK, f"{len(files)} files · {total_kb:.0f} KiB"


def _check_art() -> tuple[Level, str]:
    from timmytest.tui import pixelart

    sprites = {
        "timmy": pixelart.timmy_sprite(),
        "wordmark": pixelart.wordmark_sprite(),
        "logo": pixelart.logo_sprite(),
    }
    broken = [name for name, sprite in sprites.items() if sprite.width < 8 or sprite.height < 8]
    if broken:
        return Level.FAIL, "corrupt sprites: " + ", ".join(broken)
    pixels = sum(s.width * s.height for s in sprites.values())
    return Level.OK, f"{len(sprites)} sprites · {pixels / 1000:.0f}k pixels"


def _check_runners() -> tuple[Level, str]:
    from timmytest.detector.models import Ecosystem
    from timmytest.runner.orchestrator import run_project_tests  # noqa: F401

    return Level.OK, f"{len(list(Ecosystem))} ecosystems registered"


def _check_templates() -> tuple[Level, str]:
    from timmytest.integrations import templates

    generators = [n for n in dir(templates) if n.startswith("get_") and callable(getattr(templates, n))]
    if not generators:
        return Level.WARN, "no agent templates found"
    return Level.OK, f"{len(generators)} agent templates"


def _check_version() -> tuple[Level, str]:
    return Level.OK, f"TimmyTest {__version__}"


def _check_state_file() -> tuple[Level, str]:
    from timmytest.tui.state import STATE_FILE, AppState

    state = AppState.load()
    if STATE_FILE.exists():
        return Level.OK, f"{len(state.workspaces)} workspaces restored"
    return Level.OK, "fresh install"


def integrity_checks() -> list[Check]:
    return [
        Check("modules", "Core modules", _check_modules),
        Check("tree", "Package tree", _check_package_tree),
        Check("art", "Pixel-art assets", _check_art),
        Check("runners", "Test runners", _check_runners),
        Check("templates", "Agent templates", _check_templates),
        Check("state", "Saved state", _check_state_file),
        Check("version", "Version manifest", _check_version),
    ]


def summarise(results: list[CheckResult]) -> tuple[int, int, int]:
    """Return (passed, warnings, failures)."""
    passed = sum(1 for r in results if r.level is Level.OK)
    warned = sum(1 for r in results if r.level is Level.WARN)
    failed = sum(1 for r in results if r.level is Level.FAIL)
    return passed, warned, failed
