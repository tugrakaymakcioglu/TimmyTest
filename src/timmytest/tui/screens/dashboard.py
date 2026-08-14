"""The workspace dashboard: charts on the right, dozens of features on the left."""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, OptionList, Static
from textual.widgets.option_list import Option

from timmytest.integrations.installer import integrate_project
from timmytest.prompt.clipboard import copy_to_clipboard
from timmytest.reports.json_export import export_audit_to_json
from timmytest.scaffolder.init_tests import initialize_test_scaffold
from timmytest.tui.charts import ACCENT, CREAM, FAIL, MUTED, PASS, SKIP
from timmytest.tui.features import accent_for, default_feature_key, enabled_groups
from timmytest.tui.panels import Panels, resolve_export_path
from timmytest.tui.screens.base import TimmyScreen
from timmytest.tui.widgets import Badge

DISCORD_HOSTS = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")

INTEGRATION_FLAGS = {
    "claude": "include_claude",
    "cursor": "include_cursor",
    "copilot": "include_copilot",
    "agents": "include_agents",
    "mcp": "include_mcp",
    "ci": "include_ci",
}


class DashboardScreen(TimmyScreen):
    """Stage eight: the actual tool."""

    BINDINGS = [
        ("r", "run", "run"),
        ("ctrl+r", "run", "run"),
        ("f5", "run", "run"),
        ("tab", "focus_next_pane", "pane"),
        ("q", "close_workspace", "workspaces"),
        ("escape", "close_workspace", "workspaces"),
        ("ctrl+q", "quit_app", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._panels = Panels(self)
        self._current = default_feature_key()
        self._rendered: str | None = None
        self._rendering = False

    # -- layout ------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        with Container(id="dash-root"):
            with Horizontal(id="dash-header"):
                yield Badge(id="dash-badge")
                yield Static(id="dash-title")
                yield Button(self.t("dash.run"), id="dash-run", variant="success")
                yield Button(self.t("dash.exit_ws"), id="dash-quit", variant="error")
            with Horizontal(id="dash-body"):
                yield OptionList(id="dash-sidebar")
                yield VerticalScroll(id="dash-content")
            yield Static(id="dash-footer")

    def on_mount(self) -> None:
        self._fill_sidebar()
        self._render_header()
        self._render_footer()
        self.show_panel(self._current)
        self.query_one("#dash-sidebar", OptionList).focus()

    def _fill_sidebar(self) -> None:
        sidebar = self.query_one("#dash-sidebar", OptionList)
        sidebar.clear_options()
        options: list[Option] = []
        for group in enabled_groups():
            options.append(Option(Text(f" {self.t(group.label_key)}", style=f"bold {group.accent}"), disabled=True))
            for feature in group.features:
                label = Text()
                label.append(f"  {feature.icon}  ", style=group.accent)
                label.append(self.t(feature.label_key), style="#c9d1d9")
                options.append(Option(label, id=feature.key))
        sidebar.add_options(options)
        with_highlight = next(
            (i for i, o in enumerate(options) if o.id == self._current),
            1,
        )
        sidebar.highlighted = with_highlight

    def _render_header(self) -> None:
        workspace = self.state.active
        audit = self.timmy.audit
        title = Text()
        title.append("TIMMY", style="bold #c43e2b")
        title.append("TEST", style="bold #2f9fa8")
        if workspace:
            title.append(f"   {workspace.name}", style=f"bold {CREAM}")
            title.append(f"   {workspace.path}", style=MUTED)
        title.append("\n")
        if audit is not None:
            run = audit.test_run
            title.append(f"{audit.project.ecosystem.value}·{audit.project.test_framework.value}   ", style=ACCENT)
            title.append(f"{run.passed} ", style=PASS)
            title.append("pass  ", style=MUTED)
            title.append(f"{run.failed + run.errors} ", style=FAIL)
            title.append("fail  ", style=MUTED)
            title.append(f"{len(audit.project.test_gaps)} ", style="#a371f7")
            title.append("missing  ", style=MUTED)
            title.append(f"{audit.project.readiness_score:.0f}%", style=CREAM)
        else:
            title.append(self.t("dash.never_run"), style=MUTED)
        self.query_one("#dash-title", Static).update(title)

    def _render_footer(self) -> None:
        footer = Text()
        for key, label in [
            ("↑↓", self.t("dash.nav")),
            ("Enter", self.t("dash.select")),
            ("Tab", self.t("dash.switch")),
            ("R", self.t("dash.run")),
            ("Q", self.t("dash.exit_ws")),
        ]:
            footer.append(f" {key} ", style="bold #0d1117 on #6e7681")
            footer.append(f" {label}   ", style=MUTED)
        self.query_one("#dash-footer", Static).update(footer)

    # -- panels ------------------------------------------------------------ #

    def show_panel(self, feature_key: str) -> None:
        """Queue a panel swap; rapid arrow-key navigation collapses to the last one."""
        self._current = feature_key
        self.call_next(self._drain_panel_queue)

    async def _drain_panel_queue(self) -> None:
        # Mounting is asynchronous, so renders are serialised here: without this
        # guard, holding down an arrow key would mount two panels at once and the
        # duplicate widget ids would blow up.
        if self._rendering:
            return
        self._rendering = True
        try:
            while self._rendered != self._current:
                feature_key = self._current
                self._rendered = feature_key
                content = self.query_one("#dash-content", VerticalScroll)
                await content.remove_children()
                await content.mount_all(self._panels.build(feature_key))
                content.scroll_home(animate=False)
                content.border_title = self.t(f"f.{feature_key}")
                content.styles.border = ("round", accent_for(feature_key))
        finally:
            self._rendering = False

    def refresh_panel(self) -> None:
        self._rendered = None
        self.call_next(self._drain_panel_queue)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self.show_panel(event.option.id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.show_panel(event.option.id)
            self.query_one("#dash-content", VerticalScroll).focus()

    def _status(self, widget_id: str, message: str, style: str) -> None:
        # The panel may have been swapped out before an async result arrives.
        with contextlib.suppress(Exception):
            self.query_one(f"#{widget_id}", Static).update(Text(message, style=style))

    # -- run --------------------------------------------------------------- #

    def action_run(self) -> None:
        if self.timmy.analysis_running:
            return
        button = self.query_one("#dash-run", Button)
        button.label = self.t("dash.running")
        button.disabled = True
        self.timmy.run_analysis(self.on_analysis_finished)

    def on_analysis_finished(self, error: str | None = None) -> None:
        button = self.query_one("#dash-run", Button)
        button.label = self.t("dash.run")
        button.disabled = False
        self._render_header()
        self.refresh_panel()
        if error:
            self.timmy.log_activity(f"run failed: {error}")

    def action_focus_next_pane(self) -> None:
        sidebar = self.query_one("#dash-sidebar", OptionList)
        content = self.query_one("#dash-content", VerticalScroll)
        (content if sidebar.has_focus else sidebar).focus()

    def action_close_workspace(self) -> None:
        self.timmy.audit = None
        self.timmy.goto_workspace_gate()

    def action_quit_app(self) -> None:
        self.app.exit()

    # -- actions ------------------------------------------------------------ #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "dash-run":
            self.action_run()
        elif button_id in ("dash-quit", "dash-workspaces"):
            self.action_close_workspace()
        elif button_id == "act-copy-prompt":
            self._copy_prompt()
        elif button_id == "act-export-prompt":
            self._export_prompt()
        elif button_id == "act-export-report":
            self._export_report()
        elif button_id == "act-export-json":
            self._export_json()
        elif button_id == "act-scaffold":
            self._scaffold()
        elif button_id.startswith("act-integrate-"):
            self._integrate(button_id.removeprefix("act-integrate-"))
        elif button_id == "act-webhook-save":
            self._save_webhook()
        elif button_id == "act-discord-send":
            self._start_discord_send()
        elif button_id in ("act-lang-tr", "act-lang-en"):
            self._switch_language(button_id.removeprefix("act-lang-"))
        elif button_id == "act-ws-new":
            self.timmy.goto_workspace_form()
        elif button_id.startswith("act-ws-switch-"):
            self._switch_workspace(button_id.removeprefix("act-ws-switch-"))
        elif button_id.startswith("act-ws-remove-"):
            self._remove_workspace(button_id.removeprefix("act-ws-remove-"))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        checkbox_id = event.checkbox.id or ""
        if checkbox_id.startswith("variant-"):
            self._set_variant(checkbox_id.removeprefix("variant-"), event.value)
        elif checkbox_id.startswith("rule-"):
            self._set_rule(checkbox_id.removeprefix("rule-"), event.value)

    # -- prompt actions ------------------------------------------------------ #

    def _copy_prompt(self) -> None:
        prompt = self._panels._prompt_text()
        if copy_to_clipboard(prompt):
            self._status("act-copy-status", f"✓ {self.t('p.copy_done')}", PASS)
            self.timmy.log_activity("prompt copied to clipboard")
        else:
            self._status("act-copy-status", f"! {self.t('p.copy_fail')}", SKIP)

    def _export_prompt(self) -> None:
        target = resolve_export_path(
            self.query_one("#act-export-path", Input).value, Path("timmytest-prompt.md")
        )
        self._write(target, self._panels._prompt_text(), "act-export-status")

    def _export_report(self) -> None:
        audit = self.timmy.audit
        if audit is None:
            return
        target = resolve_export_path(
            self.query_one("#act-report-path", Input).value, Path("timmytest-report.md")
        )
        self._write(target, audit.summary_markdown, "act-report-status")

    def _export_json(self) -> None:
        audit = self.timmy.audit
        if audit is None:
            return
        target = resolve_export_path(
            self.query_one("#act-json-path", Input).value, Path("timmytest-audit.json")
        )
        self._write(target, export_audit_to_json(audit), "act-json-status")

    def _write(self, target: Path, content: str, status_id: str) -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            self._status(status_id, f"✗ {exc.strerror or exc}", FAIL)
            return
        self._status(status_id, f"✓ {self.t('p.export_done')}: {target}", PASS)
        self.timmy.log_activity(f"exported {target}")

    def _set_variant(self, variant: str, value: bool) -> None:
        if not value:
            return
        self.timmy.prompt_variant = variant
        for checkbox in self.query(Checkbox):
            if checkbox.id and checkbox.id.startswith("variant-") and checkbox.id != f"variant-{variant}":
                checkbox.value = False
        self._status("act-variant-status", f"✓ {variant}", PASS)

    # -- integrations -------------------------------------------------------- #

    def _integrate(self, flag: str) -> None:
        workspace = self.state.active
        if workspace is None or flag not in INTEGRATION_FLAGS:
            return
        options = dict.fromkeys(INTEGRATION_FLAGS.values(), False)
        options[INTEGRATION_FLAGS[flag]] = True
        try:
            result = integrate_project(project_dir=workspace.root, **options)
        except Exception as exc:
            self._status("act-integrate-status", f"✗ {type(exc).__name__}: {exc}", FAIL)
            return
        written = len(result.created_files) + len(result.modified_files)
        self._status(
            "act-integrate-status",
            f"✓ {self.t('p.applied')} — {written} {self.t('p.files_written')}",
            PASS,
        )
        self.timmy.log_activity(f"integrated {flag}: {written} files")

    def _scaffold(self) -> None:
        audit = self.timmy.audit
        workspace = self.state.active
        if audit is None or workspace is None:
            return
        try:
            created = initialize_test_scaffold(audit.project, workspace.root)
        except Exception as exc:
            self._status("act-scaffold-status", f"✗ {type(exc).__name__}: {exc}", FAIL)
            return
        self._status(
            "act-scaffold-status",
            f"✓ {len(created)} {self.t('p.files_written')}",
            PASS if created else MUTED,
        )
        self.timmy.log_activity(f"scaffolded {len(created)} test files")

    # -- discord -------------------------------------------------------------- #

    def _save_webhook(self) -> None:
        workspace = self.state.active
        if workspace is None:
            return
        url = self.query_one("#act-webhook-input", Input).value.strip()
        if url and not url.startswith(DISCORD_HOSTS):
            self._status("act-webhook-status", f"✗ {self.t('p.webhook_invalid')}", FAIL)
            return
        workspace.webhook = url
        self.state.save()
        self._status("act-webhook-status", f"✓ {self.t('p.webhook_saved')}", PASS)
        self.timmy.log_activity("discord webhook saved")

    def _set_rule(self, rule: str, value: bool) -> None:
        workspace = self.state.active
        if workspace is None:
            return
        if rule == "fail":
            workspace.notify_on_fail = value
        elif rule == "pass":
            workspace.notify_on_pass = value
        elif rule == "gaps":
            workspace.notify_on_gaps = value
        self.state.save()
        self._status("act-rules-status", f"✓ {self.t('p.save')}", PASS)

    def _start_discord_send(self) -> None:
        workspace = self.state.active
        if workspace is None or not workspace.webhook:
            self._status("act-discord-status", f"! {self.t('p.webhook_missing')}", SKIP)
            return
        message = self._panels._discord_message()
        if not message:
            return
        self._status("act-discord-status", self.t("p.sending"), MUTED)
        self.query_one("#act-discord-send", Button).disabled = True
        self._post_to_discord(workspace.webhook, message)

    @work(thread=True, exclusive=True, group="discord")
    def _post_to_discord(self, url: str, content: str) -> None:
        if not url.startswith(DISCORD_HOSTS):
            self.app.call_from_thread(self._discord_result, False, "invalid webhook host")
            return
        payload = json.dumps({"content": content}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "TimmyTest"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 - host is validated above
                ok = 200 <= response.status < 300
                detail = str(response.status)
        except urllib.error.HTTPError as exc:
            ok, detail = False, f"HTTP {exc.code}"
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}"
        self.app.call_from_thread(self._discord_result, ok, detail)

    def _discord_result(self, ok: bool, detail: str) -> None:
        message = f"{self.t('p.sent')} ({detail})" if ok else f"{self.t('p.send_failed')} — {detail}"
        self.timmy.last_discord_result = message
        self._status("act-discord-status", ("✓ " if ok else "✗ ") + message, PASS if ok else FAIL)
        with contextlib.suppress(Exception):
            self.query_one("#act-discord-send", Button).disabled = False
        self.timmy.log_activity(f"discord send: {message}")

    # -- settings -------------------------------------------------------------- #

    def _switch_language(self, code: str) -> None:
        self.t.set_language(code)
        self.state.language = code
        self.state.save()
        self.timmy.log_activity(f"language: {code}")
        self.timmy.goto_dashboard()

    def _switch_workspace(self, workspace_id: str) -> None:
        if self.state.get(workspace_id) is None:
            return
        self.state.active_workspace = workspace_id
        self.state.save()
        self.timmy.audit = None
        self.timmy.goto_dashboard()

    def _remove_workspace(self, workspace_id: str) -> None:
        self.state.remove(workspace_id)
        self.state.save()
        if not self.state.workspaces:
            self.timmy.audit = None
            self.timmy.goto_workspace_gate()
            return
        self.timmy.audit = None
        self.timmy.goto_dashboard()
