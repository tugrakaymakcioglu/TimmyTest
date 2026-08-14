"""Language selection: Türkçe or English."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal
from textual.widgets import Static

from timmytest.tui.screens.base import TimmyScreen

OPTIONS: list[tuple[str, str, str, str]] = [
    # (code, flag-ish mark, native name, description key)
    ("tr", "TR", "Türkçe", "lang.tr_desc"),
    ("en", "EN", "English", "lang.en_desc"),
]


class LanguageScreen(TimmyScreen):
    """Stage three: pick the interface language before the final configuration."""

    BINDINGS = [
        ("left", "move(-1)", "left"),
        ("right", "move(1)", "right"),
        ("up", "move(-1)", "up"),
        ("down", "move(1)", "down"),
        ("tab", "move(1)", "next"),
        ("enter", "confirm", "confirm"),
        ("t", "pick('tr')", "türkçe"),
        ("e", "pick('en')", "english"),
        ("q", "quit_app", "quit"),
        ("escape", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._index = next((i for i, o in enumerate(OPTIONS) if o[0] == self.timmy.t.language), 0)

    def compose(self) -> ComposeResult:
        with Container(id="lang-root"):
            yield Static(id="lang-title")
            with Center(), Horizontal(id="lang-cards"):
                for code, _, _, _ in OPTIONS:
                    yield Static(id=f"lang-card-{code}", classes="lang-card")
            yield Static(id="lang-hint")

    def on_mount(self) -> None:
        self._redraw()

    # -- rendering -------------------------------------------------------- #

    def _redraw(self) -> None:
        title = Text()
        title.append(self.t("lang.title"), style="bold #f3e2b8")
        title.append("\n")
        title.append(self.t("lang.subtitle"), style="#6e7681")
        self.query_one("#lang-title", Static).update(title)

        for index, (code, mark, native, desc_key) in enumerate(OPTIONS):
            card = self.query_one(f"#lang-card-{code}", Static)
            selected = index == self._index
            accent = "#c43e2b" if code == "tr" else "#2f9fa8"
            body = Group(
                Align.center(Text(mark, style=f"bold {accent}" if selected else "#484f58")),
                Align.center(Text("")),
                Align.center(Text(native, style="bold #f3e2b8" if selected else "#8b949e")),
                Align.center(Text(self.t(desc_key), style="#8b949e" if selected else "#484f58")),
            )
            card.update(body)
            card.set_class(selected, "selected")

        hint = Text()
        hint.append(self.t("lang.hint"), style="#6e7681")
        self.query_one("#lang-hint", Static).update(hint)

    # -- actions ---------------------------------------------------------- #

    def action_move(self, delta: int) -> None:
        self._index = (self._index + delta) % len(OPTIONS)
        # Preview the language live so the choice is obvious before confirming.
        self.t.set_language(OPTIONS[self._index][0])
        self._redraw()

    def action_pick(self, code: str) -> None:
        self._index = next((i for i, o in enumerate(OPTIONS) if o[0] == code), self._index)
        self.t.set_language(code)
        self._redraw()

    def action_confirm(self) -> None:
        code = OPTIONS[self._index][0]
        self.t.set_language(code)
        self.state.language = code
        self.state.save()
        self.timmy.goto_finalize()

    def on_click(self, event: events.Click) -> None:
        widget_id = getattr(getattr(event, "widget", None), "id", "") or ""
        if widget_id.startswith("lang-card-"):
            self.action_pick(widget_id.removeprefix("lang-card-"))
            self.action_confirm()
