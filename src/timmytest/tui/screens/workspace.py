"""Workspace creation: the gate, the form and the 'preparing' stage."""

from __future__ import annotations

import contextlib
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container, Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, OptionList, Static
from textual.widgets.option_list import Option

from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.tui.screens.base import TimmyScreen
from timmytest.tui.state import AI_VENDORS, Workspace, normalise_dropped_path
from timmytest.tui.widgets import LoadingBar

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class WorkspaceGateScreen(TimmyScreen):
    """Stage five: the 'create a workspace' invitation."""

    BINDINGS = [
        ("enter", "create", "create"),
        ("n", "create", "new"),
        ("q", "quit_app", "quit"),
        ("escape", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="gate-root"):
            yield Static(id="gate-title")
            yield Static(id="gate-desc")
            with Center(), Horizontal(id="gate-buttons"):
                yield Button(self.t("ws.create"), id="gate-create", variant="success")
                if self.state.workspaces:
                    yield Button(self.t("ws.open_existing"), id="gate-open")
                yield Button(self.t("setup.quit"), id="gate-quit", variant="error")
            yield OptionList(id="gate-list")
            yield Static(id="gate-existing")

    def on_mount(self) -> None:
        title = Text(self.t("ws.gate_title"), style="bold #f3e2b8")
        self.query_one("#gate-title", Static).update(title)
        self.query_one("#gate-desc", Static).update(Text(self.t("ws.gate_desc"), style="#8b949e"))

        gate_list = self.query_one("#gate-list", OptionList)
        if self.state.workspaces:
            gate_list.display = True
            gate_list.clear_options()
            options: list[Option] = []
            for ws in self.state.workspaces:
                label = Text()
                label.append(f"  ●  {ws.name}  ", style="bold #2f9fa8")
                label.append(f" {ws.path}", style="#8b949e")
                options.append(Option(label, id=ws.id))
            gate_list.add_options(options)
            target_idx = next(
                (i for i, ws in enumerate(self.state.workspaces) if ws.id == self.state.active_workspace),
                len(options) - 1,
            )
            gate_list.highlighted = target_idx
            self.call_after_refresh(gate_list.focus)
        else:
            gate_list.display = False
            self.call_after_refresh(self._focus_gate_create)

    def _focus_gate_create(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#gate-create", Button).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self._open_workspace(event.option.id)

    def _open_workspace(self, ws_id: str) -> None:
        if self.state.get(ws_id) is not None:
            self.state.active_workspace = ws_id
            self.state.save()
            self.timmy.audit = None
            self.timmy.goto_dashboard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gate-create":
            self.action_create()
        elif event.button.id == "gate-open":
            self.action_open()
        elif event.button.id == "gate-quit":
            self.action_quit_app()

    def action_create(self) -> None:
        self.timmy.goto_workspace_form()

    def action_open(self) -> None:
        if self.state.workspaces:
            active_id = self.state.active_workspace or self.state.workspaces[-1].id
            self._open_workspace(active_id)

    def action_quit_app(self) -> None:
        self.app.exit()


class WorkspaceFormScreen(TimmyScreen):
    """Stage six: name, vendors and project path."""

    BINDINGS = [
        ("escape", "back", "back"),
        ("ctrl+s", "create", "create"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._resolved: Path | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="form-root"):
            yield Static(id="form-title")

            yield Static(self.t("ws.name"), classes="field-label")
            yield Input(placeholder=self.t("ws.name_ph"), id="form-name")

            yield Static(id="form-agents-label", classes="field-label")
            with Grid(id="form-agents"):
                for code, label in AI_VENDORS:
                    yield Checkbox(label, id=f"vendor-{code}")

            yield Static(id="form-path-label", classes="field-label")
            yield Input(placeholder=self.t("ws.path_ph"), id="form-path")
            yield Static(id="form-path-status")
            yield Static(id="form-detected")

            yield Static(id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button(self.t("ws.create_btn"), id="form-create", variant="success")
                yield Button(self.t("ws.back"), id="form-back")

    def on_mount(self) -> None:
        self.query_one("#form-title", Static).update(Text(self.t("ws.form_title"), style="bold #f3e2b8"))

        agents_label = Text()
        agents_label.append(self.t("ws.agents"), style="bold #c9d1d9")
        agents_label.append(f"   {self.t('ws.agents_hint')}", style="#6e7681")
        self.query_one("#form-agents-label", Static).update(agents_label)

        path_label = Text()
        path_label.append(self.t("ws.path"), style="bold #c9d1d9")
        path_label.append(f"   {self.t('ws.path_hint')}", style="#6e7681")
        self.query_one("#form-path-label", Static).update(path_label)

        self.query_one("#form-name", Input).focus()

    # -- live path resolution --------------------------------------------- #

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "form-path":
            self._resolve_path(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "form-name":
            self.query_one("#form-path", Input).focus()
        elif event.input.id == "form-path":
            self.action_create()

    def _resolve_path(self, raw: str) -> None:
        status = self.query_one("#form-path-status", Static)
        detected = self.query_one("#form-detected", Static)
        self._resolved = None

        if not raw.strip():
            status.update(Text(self.t("ws.path_empty"), style="#6e7681"))
            detected.update(Text(""))
            return

        resolved = normalise_dropped_path(raw)
        if resolved is None:
            status.update(Text(f"✗ {self.t('ws.path_missing')}", style="#f85149"))
            detected.update(Text(""))
            return

        self._resolved = resolved
        dropped_a_file = Path(raw.strip().strip("\"'")).is_file()
        message = self.t("ws.path_file") if dropped_a_file else self.t("ws.path_ok")
        text = Text()
        text.append("✓ ", style="#3fb950")
        text.append(message, style="#3fb950")
        text.append(f"   {resolved}", style="#8b949e")
        status.update(text)

        # Auto-fill the project name from the folder once, as a convenience.
        name_input = self.query_one("#form-name", Input)
        if not name_input.value.strip():
            name_input.value = resolved.name

        try:
            ecosystem, framework, command, configs = detect_ecosystem(resolved)
        except Exception:
            detected.update(Text(""))
            return

        info = Table.grid(padding=(0, 2))
        info.add_column(style="#6e7681", justify="right")
        info.add_column(style="#c9d1d9")
        info.add_row(self.t("ws.detected"), f"{ecosystem.value} · {framework.value}")
        info.add_row(self.t("p.command"), command or "—")
        if configs:
            info.add_row("config", ", ".join(configs[:6]))
        detected.update(info)

    # -- actions ---------------------------------------------------------- #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "form-create":
            self.action_create()
        elif event.button.id == "form-back":
            self.action_back()

    def _selected_vendors(self) -> list[str]:
        return [
            code
            for code, _ in AI_VENDORS
            if self.query_one(f"#vendor-{code}", Checkbox).value
        ]

    def action_create(self) -> None:
        error = self.query_one("#form-error", Static)
        name = self.query_one("#form-name", Input).value.strip()
        vendors = self._selected_vendors()

        problems = []
        if not name:
            problems.append(self.t("ws.err_name"))
        if not vendors:
            problems.append(self.t("ws.err_agents"))
        if self._resolved is None:
            problems.append(self.t("ws.err_path"))
        if problems:
            error.update(Text("✗ " + "   ".join(problems), style="#f85149"))
            return

        assert self._resolved is not None
        error.update(Text(""))
        workspace = Workspace(name=name, path=str(self._resolved), vendors=vendors)
        self.timmy.goto_preparing(workspace)

    def action_back(self) -> None:
        self.timmy.goto_workspace_gate()


class PreparingScreen(TimmyScreen):
    """Stage seven: 'preparing and verifying' while the first scan runs."""

    BINDINGS = [
        ("q", "quit_app", "quit"),
        ("escape", "quit_app", "quit"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    STEPS = [
        "prep.step.register",
        "prep.step.ecosystem",
        "prep.step.scan",
        "prep.step.gaps",
        "prep.step.prompt",
        "prep.step.dashboard",
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self._workspace = workspace
        self._done = 0
        self._frame = 0
        self._scan_finished = False
        self._finished = False

    def compose(self) -> ComposeResult:
        with Container(id="prep-root"):
            yield Static(id="prep-title")
            with Center():
                yield Static(id="prep-steps")
            with Center():
                yield LoadingBar(colour="#2f9fa8", id="prep-bar")
            yield Static(id="prep-status")

    def on_mount(self) -> None:
        title = Text()
        title.append(self.t("prep.title"), style="bold #f3e2b8")
        title.append(f"\n{self._workspace.name}  ·  {self._workspace.path}", style="#6e7681")
        self.query_one("#prep-title", Static).update(title)
        self._redraw()
        self.set_interval(0.18, self._tick)
        self.timmy.start_initial_scan(self._workspace, self._on_scan_done)

    def _on_scan_done(self) -> None:
        self._scan_finished = True

    def _tick(self) -> None:
        if self._finished:
            return
        self._frame += 1
        # The last step waits for the background scan so the dashboard opens with data.
        last = len(self.STEPS) - 1
        if self._done < last or (self._done == last and self._scan_finished):
            self._done += 1
            self.query_one("#prep-bar", LoadingBar).set_percent(self._done / len(self.STEPS) * 100)
        self._redraw()
        if self._done >= len(self.STEPS):
            self._finished = True
            self.set_timer(0.4, self.timmy.goto_dashboard)

    def _redraw(self) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(width=2, no_wrap=True)
        table.add_column(no_wrap=True)
        for index, key in enumerate(self.STEPS):
            if index < self._done:
                glyph, style = Text("✓", style="bold #3fb950"), "#8b949e"
            elif index == self._done:
                glyph, style = Text(SPINNER[self._frame % len(SPINNER)], style="#2f9fa8"), "#f3e2b8"
            else:
                glyph, style = Text("·", style="#30363d"), "#484f58"
            table.add_row(glyph, Text(self.t(key), style=style))
        self.query_one("#prep-steps", Static).update(table)

        status = Text()
        if self._done >= len(self.STEPS):
            status.append("✓ ", style="bold #3fb950")
            status.append(self.t("prep.done"), style="bold #3fb950")
        self.query_one("#prep-status", Static).update(status)
