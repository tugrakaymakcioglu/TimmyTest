"""Full-screen pixel-art splash with a white loading bar."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from timmytest import __version__
from timmytest.banner import AUTHOR
from timmytest.tui import pixelart
from timmytest.tui.screens.base import TimmyScreen
from timmytest.tui.widgets import LoadingBar, PixelArt

# (percentage the bar stops at, translation key for the status line)
BOOT_STEPS: list[tuple[int, str]] = [
    (18, "splash.step.core"),
    (37, "splash.step.detector"),
    (58, "splash.step.runners"),
    (76, "splash.step.agents"),
    (92, "splash.step.mcp"),
    (100, "splash.step.ready"),
]

TICK = 1 / 30
STEP_PER_TICK = 1.9
HOLD_AFTER_FULL = 0.45


class SplashScreen(TimmyScreen):
    """Stage one: the logo fills the terminal while the bar fills up to 100%."""

    BINDINGS = [
        ("escape", "skip", "skip"),
        ("enter", "skip", "skip"),
        ("space", "skip", "skip"),
        ("q", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._percent = 0.0
        self._step = 0
        self._done = False

    def compose(self) -> ComposeResult:
        with Container(id="splash-root"):
            yield PixelArt(pixelart.compose_hero, id="splash-hero")
            with Container(id="splash-footer"):
                with Horizontal(id="splash-status-row"):
                    yield Static(id="splash-status")
                    yield Static(id="splash-percent")
                yield LoadingBar(id="splash-bar")
                yield Static(
                    Text(f"TimmyTest v{__version__}  ·  {AUTHOR}", style="#6e7681"),
                    id="splash-version",
                )

    def on_mount(self) -> None:
        self._render_status()
        self.set_interval(TICK, self._tick)

    def _tick(self) -> None:
        if self._done:
            return
        target = BOOT_STEPS[self._step][0]
        self._percent = min(target, self._percent + STEP_PER_TICK)
        self.query_one("#splash-bar", LoadingBar).set_percent(self._percent)
        self.query_one("#splash-percent", Static).update(
            Text(f"{int(self._percent):3d}%", style="bold #ffffff")
        )
        if self._percent >= target:
            if self._step + 1 < len(BOOT_STEPS):
                self._step += 1
                self._render_status()
            else:
                self._done = True
                self.set_timer(HOLD_AFTER_FULL, self._advance)

    def _render_status(self) -> None:
        text = Text()
        text.append("▌ ", style="#c43e2b")
        text.append(self.t(BOOT_STEPS[self._step][1]), style="#f3e2b8")
        text.append(" …", style="#6e7681")
        self.query_one("#splash-status", Static).update(text)

    def _advance(self) -> None:
        self.timmy.goto_setup()

    def action_skip(self) -> None:
        if self._done:
            return
        self._done = True
        self.query_one("#splash-bar", LoadingBar).set_percent(100)
        self._advance()
