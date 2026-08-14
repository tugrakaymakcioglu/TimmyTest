"""The TimmyTest terminal application: splash → setup → language → workspace → dashboard."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App

from timmytest.analysis import analyze_project
from timmytest.detector.models import ProjectAudit
from timmytest.tui.i18n import Translator
from timmytest.tui.screens.dashboard import DashboardScreen
from timmytest.tui.screens.finalize import FinalizeScreen
from timmytest.tui.screens.language import LanguageScreen
from timmytest.tui.screens.setup import SetupScreen
from timmytest.tui.screens.splash import SplashScreen
from timmytest.tui.screens.workspace import (
    PreparingScreen,
    WorkspaceFormScreen,
    WorkspaceGateScreen,
)
from timmytest.tui.state import AppState, RunSnapshot, Workspace, utc_now

MAX_ACTIVITY = 500


class TimmyApp(App[None]):
    """Keyboard-driven front end for the whole TimmyTest toolchain."""

    CSS_PATH = "styles.tcss"
    TITLE = "TimmyTest"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        ("ctrl+c", "quit_app", "Quit"),
        ("ctrl+q", "quit_app", "Quit"),
    ]

    def action_quit_app(self) -> None:
        self.exit()

    def __init__(self, fresh: bool = False, start_path: Path | None = None) -> None:
        super().__init__()
        self.state: AppState = AppState.load()
        self.t: Translator = Translator(self.state.language)
        self.audit: ProjectAudit | None = None
        self.activity: list[str] = []
        self.prompt_variant: str = "full"
        self.last_discord_result: str = ""
        self.analysis_running: bool = False
        self._fresh = fresh
        self._start_path = start_path

    def on_mount(self) -> None:
        self.push_screen(SplashScreen())

    # -- navigation --------------------------------------------------------- #

    def goto_setup(self) -> None:
        self.switch_screen(SetupScreen())

    def goto_after_setup(self) -> None:
        """First run walks the whole onboarding; later runs jump to the work."""
        if self._fresh or not self.state.setup_complete:
            self.switch_screen(LanguageScreen())
        elif self._start_path is not None or not self.state.workspaces:
            self.goto_workspace_gate()
        else:
            self.goto_dashboard()

    def goto_finalize(self) -> None:
        self.switch_screen(FinalizeScreen())

    def goto_workspace_gate(self) -> None:
        self.switch_screen(WorkspaceGateScreen())

    def goto_workspace_form(self) -> None:
        self.switch_screen(WorkspaceFormScreen())

    def goto_preparing(self, workspace: Workspace) -> None:
        self.switch_screen(PreparingScreen(workspace))

    def goto_dashboard(self) -> None:
        self.switch_screen(DashboardScreen())

    # -- activity log -------------------------------------------------------- #

    def log_activity(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.activity.append(f"{stamp}  {message}")
        del self.activity[:-MAX_ACTIVITY]

    # -- analysis ------------------------------------------------------------ #

    def start_initial_scan(self, workspace: Workspace, done: Callable[[], None]) -> None:
        """Register a brand new workspace and populate it with a static scan.

        The test suite is deliberately *not* executed here: creating a workspace
        should never fire off someone's whole test run behind their back. That is
        what the RUN button is for.
        """
        self._initial_scan(workspace, done)

    @work(thread=True, exclusive=True, group="analysis")
    def _initial_scan(self, workspace: Workspace, done: Callable[[], None]) -> None:
        audit: ProjectAudit | None = None
        try:
            audit = analyze_project(workspace.root, execute_tests=False)
        except Exception as exc:
            self.call_from_thread(self.log_activity, f"initial scan failed: {type(exc).__name__}: {exc}")
        self.call_from_thread(self._finish_initial_scan, workspace, audit, done)

    def _finish_initial_scan(
        self,
        workspace: Workspace,
        audit: ProjectAudit | None,
        done: Callable[[], None],
    ) -> None:
        if audit is not None:
            workspace.ecosystem = audit.project.ecosystem.value
            workspace.framework = audit.project.test_framework.value
            workspace.record(_snapshot(audit))
        self.audit = audit
        self.state.add(workspace)
        self.state.save()
        self.log_activity(f"workspace created: {workspace.name}")
        done()

    def run_analysis(self, done: Callable[[str | None], None]) -> None:
        workspace = self.state.active
        if workspace is None or self.analysis_running:
            done("no workspace")
            return
        self.analysis_running = True
        self.log_activity(f"run started: {workspace.path}")
        self._run_analysis(workspace, done)

    @work(thread=True, exclusive=True, group="analysis")
    def _run_analysis(self, workspace: Workspace, done: Callable[[str | None], None]) -> None:
        audit: ProjectAudit | None = None
        error: str | None = None
        try:
            audit = analyze_project(workspace.root, execute_tests=True)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        self.call_from_thread(self._finish_analysis, workspace, audit, error, done)

    def _finish_analysis(
        self,
        workspace: Workspace,
        audit: ProjectAudit | None,
        error: str | None,
        done: Callable[[str | None], None],
    ) -> None:
        self.analysis_running = False
        if audit is not None:
            self.audit = audit
            workspace.ecosystem = audit.project.ecosystem.value
            workspace.framework = audit.project.test_framework.value
            workspace.record(_snapshot(audit))
            self.state.save()
            run = audit.test_run
            self.log_activity(
                f"run finished: {run.passed} pass / {run.failed + run.errors} fail / "
                f"{len(audit.project.test_gaps)} missing"
            )
        done(error)


def _snapshot(audit: ProjectAudit) -> RunSnapshot:
    run = audit.test_run
    return RunSnapshot(
        timestamp=utc_now(),
        passed=run.passed,
        failed=run.failed,
        skipped=run.skipped,
        errors=run.errors,
        missing=len(audit.project.test_gaps),
        total=run.total,
        readiness=audit.project.readiness_score,
        duration=run.duration_seconds,
        executed=run.has_executed,
    )


def launch(fresh: bool = False, start_path: Path | None = None) -> None:
    """Entry point used by ``timmytest ui``."""
    import contextlib

    from timmytest.banner import maximize_terminal

    # Turkish Windows consoles default to cp1254; the UI is full of box drawing
    # and accented text, so force UTF-8 before anything is written.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8", errors="replace")

    # The splash art scales to the window, so a maximised console is worth asking
    # for. Windows Terminal ignores this; classic consoles honour it.
    maximize_terminal()
    TimmyApp(fresh=fresh, start_path=start_path).run()
