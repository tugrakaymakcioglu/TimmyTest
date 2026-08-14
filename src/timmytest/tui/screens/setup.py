"""First-run setup: system requirements and file integrity verification."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal
from textual.timer import Timer
from textual.widgets import Button, Static

from timmytest.tui import preflight
from timmytest.tui.preflight import Check, CheckResult, Level
from timmytest.tui.screens.base import TimmyScreen
from timmytest.tui.widgets import LoadingBar

GLYPHS = {Level.OK: "✓", Level.WARN: "!", Level.FAIL: "✗"}
COLOURS = {Level.OK: "#3fb950", Level.WARN: "#d29922", Level.FAIL: "#f85149"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

CHECK_INTERVAL = 0.11


class SetupScreen(TimmyScreen):
    """Stage two: prove the machine and the installation are in good shape."""

    BINDINGS = [
        ("enter", "continue", "continue"),
        ("r", "retry", "retry"),
        ("q", "quit_app", "quit"),
        ("escape", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # The Textual size is authoritative here; shutil only sees the host console.
        self._system: list[Check] = preflight.system_checks(
            terminal_size=(self.app.size.width, self.app.size.height)
        )
        self._integrity: list[Check] = preflight.integrity_checks()
        self._results: dict[str, CheckResult] = {}
        self._queue: list[tuple[str, Check]] = []
        self._frame = 0
        self._finished = False
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Container(id="setup-root"):
            yield Static(id="setup-title")
            with Horizontal(id="setup-columns"):
                yield Static(id="setup-system", classes="check-panel")
                yield Static(id="setup-integrity", classes="check-panel")
            yield LoadingBar(colour="#2f9fa8", id="setup-bar")
            yield Static(id="setup-summary")
            with Center(), Horizontal(id="setup-buttons"):
                yield Button(self.t("setup.continue"), id="setup-continue", variant="success")
                yield Button(self.t("setup.retry"), id="setup-retry")
                yield Button(self.t("setup.quit"), id="setup-quit", variant="error")

    def on_mount(self) -> None:
        title = Text()
        title.append(self.t("setup.title"), style="bold #f3e2b8")
        title.append("\n")
        title.append(self.t("setup.subtitle"), style="#6e7681")
        self.query_one("#setup-title", Static).update(title)
        self._start()

    # -- execution -------------------------------------------------------- #

    def _start(self) -> None:
        self._results.clear()
        self._finished = False
        self._queue = [("system", c) for c in self._system] + [("integrity", c) for c in self._integrity]
        self.query_one("#setup-bar", LoadingBar).set_percent(0)
        self.query_one("#setup-summary", Static).update(Text(self.t("setup.checking"), style="#6e7681"))
        for button_id in ("#setup-continue", "#setup-retry", "#setup-quit"):
            self.query_one(button_id, Button).disabled = True
        self._redraw()
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_interval(CHECK_INTERVAL, self._run_next)

    def _run_next(self) -> None:
        if self._finished:
            return
        self._frame += 1
        if not self._queue:
            self._complete()
            return
        _, check = self._queue.pop(0)
        self._results[check.key] = check.execute()
        total = len(self._system) + len(self._integrity)
        self.query_one("#setup-bar", LoadingBar).set_percent(len(self._results) / total * 100)
        self._redraw()

    def _complete(self) -> None:
        self._finished = True
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        results = list(self._results.values())
        passed, warned, failed = preflight.summarise(results)

        summary = Text()
        if failed:
            summary.append("✗ ", style="bold #f85149")
            summary.append(self.t("setup.has_errors"), style="bold #f85149")
        elif warned:
            summary.append("! ", style="bold #d29922")
            summary.append(self.t("setup.has_warnings"), style="bold #d29922")
        else:
            summary.append("✓ ", style="bold #3fb950")
            summary.append(self.t("setup.all_ready"), style="bold #3fb950")
        summary.append(
            f"   {passed} {self.t('setup.passed')} · {warned} {self.t('setup.warned')} · {failed} {self.t('setup.failed')}",
            style="#6e7681",
        )
        self.query_one("#setup-summary", Static).update(summary)

        continue_button = self.query_one("#setup-continue", Button)
        continue_button.disabled = bool(failed)
        self.query_one("#setup-retry", Button).disabled = False
        self.query_one("#setup-quit", Button).disabled = False
        (self.query_one("#setup-retry", Button) if failed else continue_button).focus()

    # -- rendering -------------------------------------------------------- #

    def _panel(self, title: str, checks: list[Check]) -> RenderableType:
        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column(width=2, no_wrap=True)
        table.add_column(ratio=2, no_wrap=True)
        table.add_column(ratio=3, justify="right", overflow="ellipsis", no_wrap=True)

        pending_seen = False
        for check in checks:
            result = self._results.get(check.key)
            if result is None:
                if pending_seen or self._finished:
                    glyph = Text("·", style="#30363d")
                    detail = Text("", style="#30363d")
                else:
                    pending_seen = True
                    glyph = Text(SPINNER[self._frame % len(SPINNER)], style="#2f9fa8")
                    detail = Text(self.t("setup.checking"), style="#6e7681")
                label_style = "#484f58"
            else:
                glyph = Text(GLYPHS[result.level], style=f"bold {COLOURS[result.level]}")
                detail = Text(result.detail, style=COLOURS[result.level] if result.level is not Level.OK else "#8b949e")
                label_style = "#c9d1d9"
            table.add_row(glyph, Text(check.label, style=label_style), detail)

        heading = Text(title, style="bold #2f9fa8")
        return Group(heading, Text(""), table)

    def _redraw(self) -> None:
        self.query_one("#setup-system", Static).update(
            self._panel(self.t("setup.requirements"), self._system)
        )
        self.query_one("#setup-integrity", Static).update(
            self._panel(self.t("setup.integrity"), self._integrity)
        )

    # -- actions ---------------------------------------------------------- #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-continue":
            self.action_continue()
        elif event.button.id == "setup-retry":
            self.action_retry()
        elif event.button.id == "setup-quit":
            self.action_quit_app()

    def action_continue(self) -> None:
        if not self._finished or self.query_one("#setup-continue", Button).disabled:
            return
        self.timmy.goto_after_setup()

    def action_retry(self) -> None:
        if self._finished:
            self._start()

    def action_quit_app(self) -> None:
        self.app.exit()
