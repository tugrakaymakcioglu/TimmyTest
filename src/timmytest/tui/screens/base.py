"""Shared screen helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.screen import Screen

if TYPE_CHECKING:
    from timmytest.tui.app import TimmyApp
    from timmytest.tui.i18n import Translator
    from timmytest.tui.state import AppState


class TimmyScreen(Screen):
    """Base screen with typed access to the application state and translator."""

    @property
    def timmy(self) -> TimmyApp:
        return cast("TimmyApp", self.app)

    @property
    def t(self) -> Translator:
        return self.timmy.t

    @property
    def state(self) -> AppState:
        return self.timmy.state

    def action_quit_app(self) -> None:
        self.app.exit()
