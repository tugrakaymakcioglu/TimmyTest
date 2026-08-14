"""Final configuration pass that runs right after the language is chosen."""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container
from textual.widgets import Static

from timmytest.tui.screens.base import TimmyScreen
from timmytest.tui.state import APP_DIR, CACHE_DIR
from timmytest.tui.widgets import LoadingBar

STEP_INTERVAL = 0.22
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class FinalizeScreen(TimmyScreen):
    """Stage four: persist the choices and warm everything up."""

    BINDINGS = [
        ("q", "quit_app", "quit"),
        ("escape", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._steps: list[tuple[str, Callable[[], None]]] = [
            ("final.step.language", self._save_language),
            ("final.step.profile", self._prepare_profile),
            ("final.step.cache", self._prepare_cache),
            ("final.step.runners", self._register_runners),
            ("final.step.agents", self._compile_templates),
            ("final.step.verify", self._verify),
        ]
        self._done = 0
        self._frame = 0
        self._finished = False

    def compose(self) -> ComposeResult:
        with Container(id="final-root"):
            yield Static(id="final-title")
            with Center():
                yield Static(id="final-steps")
            with Center():
                yield LoadingBar(colour="#f3e2b8", id="final-bar")
            yield Static(id="final-status")

    def on_mount(self) -> None:
        title = Text()
        title.append(self.t("final.title"), style="bold #f3e2b8")
        title.append("\n")
        title.append(self.t("final.subtitle"), style="#6e7681")
        self.query_one("#final-title", Static).update(title)
        self._redraw()
        self.set_interval(STEP_INTERVAL, self._advance)

    # -- steps ------------------------------------------------------------ #

    def _save_language(self) -> None:
        self.state.language = self.t.language
        self.state.save()

    def _prepare_profile(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)

    def _prepare_cache(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _register_runners(self) -> None:
        from timmytest.runner.orchestrator import run_project_tests  # noqa: F401

    def _compile_templates(self) -> None:
        from timmytest.integrations import templates  # noqa: F401

    def _verify(self) -> None:
        self.state.setup_complete = True
        self.state.save()

    # -- loop ------------------------------------------------------------- #

    def _advance(self) -> None:
        if self._finished:
            return
        self._frame += 1
        if self._done >= len(self._steps):
            self._finished = True
            self.set_timer(0.4, self.timmy.goto_workspace_gate)
            return
        # A failed convenience step must not block onboarding.
        with contextlib.suppress(Exception):
            self._steps[self._done][1]()
        self._done += 1
        self.query_one("#final-bar", LoadingBar).set_percent(self._done / len(self._steps) * 100)
        self._redraw()

    def _redraw(self) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(width=2, no_wrap=True)
        table.add_column(no_wrap=True)
        for index, (key, _) in enumerate(self._steps):
            if index < self._done:
                glyph = Text("✓", style="bold #3fb950")
                label = Text(self.t(key), style="#8b949e")
            elif index == self._done:
                glyph = Text(SPINNER[self._frame % len(SPINNER)], style="#2f9fa8")
                label = Text(self.t(key), style="#f3e2b8")
            else:
                glyph = Text("·", style="#30363d")
                label = Text(self.t(key), style="#484f58")
            table.add_row(glyph, label)
        self.query_one("#final-steps", Static).update(table)

        status = Text()
        if self._done >= len(self._steps):
            status.append("✓ ", style="bold #3fb950")
            status.append(self.t("final.done"), style="bold #3fb950")
        self.query_one("#final-status", Static).update(status)
