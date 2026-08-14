"""Persistent state for the TimmyTest terminal application.

Everything the user configures - language, workspaces, Discord webhook, run
history - lives in a single JSON file under ``~/.timmytest``.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(os.environ.get("TIMMYTEST_HOME", Path.home() / ".timmytest"))
STATE_FILE = APP_DIR / "state.json"
CACHE_DIR = APP_DIR / "cache"

AI_VENDORS: list[tuple[str, str]] = [
    ("anthropic", "Anthropic · Claude Code"),
    ("openai", "OpenAI · Codex"),
    ("google", "Google · Gemini / Antigravity"),
    ("github", "GitHub · Copilot"),
    ("cursor", "Cursor"),
    ("xai", "xAI · Grok"),
    ("meta", "Meta · Llama"),
    ("mistral", "Mistral AI"),
    ("deepseek", "DeepSeek"),
    ("qwen", "Alibaba · Qwen"),
]

MAX_HISTORY = 40


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class RunSnapshot:
    """One analysis result, small enough to keep dozens of them around."""

    timestamp: str = ""
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    missing: int = 0
    total: int = 0
    readiness: float = 0.0
    duration: float = 0.0
    executed: bool = False

    @property
    def has_data(self) -> bool:
        return bool(self.timestamp)


@dataclass
class Workspace:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    path: str = ""
    vendors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    ecosystem: str = "unknown"
    framework: str = "unknown"
    webhook: str = ""
    notify_on_fail: bool = True
    notify_on_pass: bool = False
    notify_on_gaps: bool = False
    last_run: RunSnapshot = field(default_factory=RunSnapshot)
    history: list[RunSnapshot] = field(default_factory=list)

    @property
    def root(self) -> Path:
        return Path(self.path)

    def record(self, snapshot: RunSnapshot) -> None:
        self.last_run = snapshot
        self.history.append(snapshot)
        del self.history[:-MAX_HISTORY]


@dataclass
class AppState:
    language: str = "tr"
    setup_complete: bool = False
    active_workspace: str | None = None
    workspaces: list[Workspace] = field(default_factory=list)

    # -- lookup ---------------------------------------------------------- #

    def get(self, workspace_id: str | None) -> Workspace | None:
        if not workspace_id:
            return None
        return next((w for w in self.workspaces if w.id == workspace_id), None)

    @property
    def active(self) -> Workspace | None:
        return self.get(self.active_workspace)

    def add(self, workspace: Workspace) -> Workspace:
        self.workspaces.append(workspace)
        self.active_workspace = workspace.id
        return workspace

    def remove(self, workspace_id: str) -> None:
        self.workspaces = [w for w in self.workspaces if w.id != workspace_id]
        if self.active_workspace == workspace_id:
            self.active_workspace = self.workspaces[-1].id if self.workspaces else None

    # -- persistence ------------------------------------------------------ #

    @classmethod
    def load(cls) -> AppState:
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()

        workspaces = []
        for item in raw.get("workspaces", []):
            if not isinstance(item, dict):
                continue
            workspaces.append(_workspace_from_dict(item))

        return cls(
            language=raw.get("language", "tr"),
            setup_complete=bool(raw.get("setup_complete", False)),
            active_workspace=raw.get("active_workspace"),
            workspaces=workspaces,
        )

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "language": self.language,
            "setup_complete": self.setup_complete,
            "active_workspace": self.active_workspace,
            "workspaces": [asdict(w) for w in self.workspaces],
        }
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)


def _snapshot_from_dict(data: Any) -> RunSnapshot:
    if not isinstance(data, dict):
        return RunSnapshot()
    known = {f for f in RunSnapshot.__dataclass_fields__}
    return RunSnapshot(**{k: v for k, v in data.items() if k in known})


def _workspace_from_dict(data: dict[str, Any]) -> Workspace:
    known = {f for f in Workspace.__dataclass_fields__} - {"last_run", "history"}
    workspace = Workspace(**{k: v for k, v in data.items() if k in known})
    workspace.last_run = _snapshot_from_dict(data.get("last_run"))
    workspace.history = [_snapshot_from_dict(item) for item in data.get("history", [])]
    return workspace


# --------------------------------------------------------------------------- #
# Path handling for pasted / dropped folders
# --------------------------------------------------------------------------- #

_DROP_PREFIXES = ("& ", "cd ", "Set-Location ")
_FILE_URI = re.compile(r"^file:///?", re.IGNORECASE)


def normalise_dropped_path(raw: str) -> Path | None:
    """Turn whatever a terminal produces on drag & drop into a real directory.

    Terminals wrap dropped paths in quotes, PowerShell prefixes them with ``& ``,
    file managers may hand over a ``file://`` URI, and dropping a *file* should
    still select the folder that contains it.
    """
    text = raw.strip()
    if not text:
        return None

    for prefix in _DROP_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()

    if _FILE_URI.match(text):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(text)
        text = unquote(parsed.path)
        # file:///C:/x -> /C:/x on Windows
        if re.match(r"^/[A-Za-z]:", text):
            text = text[1:]

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]

    text = text.strip()
    # Trailing separators are noise, except on a bare drive root such as "C:\".
    while len(text) > 3 and text[-1] in "\\/":
        text = text[:-1]
    if not text:
        return None

    try:
        path = Path(os.path.expandvars(text)).expanduser()
    except (OSError, ValueError):
        return None

    if path.is_file():
        path = path.parent
    if not path.is_dir():
        return None
    try:
        return path.resolve()
    except OSError:
        return path
