"""Content panels for every sidebar feature of the dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Static

from timmytest import __version__
from timmytest.config import load_project_config
from timmytest.detector.models import ProjectAudit
from timmytest.tui import charts
from timmytest.tui.charts import ACCENT, CREAM, FAIL, MISS, MUTED, PASS, SKIP
from timmytest.tui.features import GROUPS
from timmytest.tui.state import AI_VENDORS, STATE_FILE, Workspace

if TYPE_CHECKING:
    from timmytest.tui.screens.dashboard import DashboardScreen

PRIORITY_COLOURS = {"HIGH": FAIL, "MEDIUM": SKIP, "LOW": ACCENT}

PROMPT_VARIANTS = [
    ("full", "Full audit prompt"),
    ("failures", "Failures only"),
    ("gaps", "Missing tests only"),
]


def _text(value: str, style: str = "") -> Static:
    return Static(Text(value, style=style))


def _heading(title: str, subtitle: str = "") -> Static:
    text = Text()
    text.append(title, style=f"bold {CREAM}")
    if subtitle:
        text.append(f"\n{subtitle}", style=MUTED)
    return Static(text, classes="panel-heading")


class Panels:
    """Builds the widget list for a feature, using whatever data is loaded."""

    def __init__(self, screen: DashboardScreen) -> None:
        self.screen = screen
        self.t = screen.t

    # -- shared helpers --------------------------------------------------- #

    @property
    def audit(self) -> ProjectAudit | None:
        return self.screen.timmy.audit

    @property
    def workspace(self) -> Workspace | None:
        return self.screen.state.active

    def _needs_data(self) -> list[Widget]:
        return [_text(self.t("p.no_data"), MUTED)]

    def build(self, feature_key: str) -> list[Widget]:
        builder = getattr(self, f"panel_{feature_key}", None)
        if builder is None:
            return [_text(feature_key, MUTED)]
        try:
            return builder()
        except Exception as exc:  # a broken panel should not take the app down
            return [_text(f"{type(exc).__name__}: {exc}", FAIL)]

    def counts(self) -> tuple[int, int, int, int]:
        audit = self.audit
        if audit is None:
            return 0, 0, 0, 0
        run = audit.test_run
        return run.passed, run.failed + run.errors, run.skipped, len(audit.project.test_gaps)

    # -- overview --------------------------------------------------------- #

    def panel_overview(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.overview")), *self._needs_data()]

        passed, failed, skipped, missing = self.counts()
        tiles = charts.stat_row(
            [
                charts.stat_tile(self.t("p.tests_passed"), passed, PASS),
                charts.stat_tile(self.t("p.tests_failed"), failed, FAIL),
                charts.stat_tile(self.t("p.tests_skipped"), skipped, SKIP),
                charts.stat_tile(self.t("p.tests_missing"), missing, MISS),
            ]
        )

        distribution = charts.distribution_chart(
            [
                (self.t("p.tests_passed"), passed, PASS),
                (self.t("p.tests_failed"), failed, FAIL),
                (self.t("p.tests_skipped"), skipped, SKIP),
                (self.t("p.tests_missing"), missing, MISS),
            ],
            width=38,
        )

        project = audit.project
        info = charts.kv_table(
            [
                (self.t("p.ecosystem"), Text(project.ecosystem.value, style=ACCENT)),
                (self.t("p.framework"), Text(project.test_framework.value, style=ACCENT)),
                (self.t("p.command"), Text(project.test_command or "—", style=CREAM)),
                (self.t("p.source_files"), Text(str(project.total_source_files))),
                (self.t("p.test_files"), Text(str(project.total_test_files))),
                (
                    self.t("p.duration"),
                    Text(f"{audit.test_run.duration_seconds:.2f}s" if audit.test_run.has_executed else "—"),
                ),
            ]
        )

        body = Table.grid(expand=True, padding=(0, 2))
        body.add_column(ratio=3)
        body.add_column(ratio=2)
        body.add_row(
            charts.section(self.t("p.distribution"), distribution),
            charts.section(self.t("dash.workspace"), info),
        )

        gauge = charts.gauge(audit.project.readiness_score, 46, self.t("p.readiness"))
        history = self.workspace.history if self.workspace else []

        widgets: list[Widget] = [
            Static(tiles, classes="tiles"),
            Static(gauge, classes="gauge"),
            Static(body),
        ]
        if len([h for h in history if h.has_data]) > 1:
            widgets.append(Static(charts.section(self.t("p.history"), charts.history_chart(history))))
        return widgets

    def panel_results(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.results")), *self._needs_data()]
        run = audit.test_run

        table = Table(expand=True, border_style=MUTED, header_style=f"bold {CREAM}")
        table.add_column(self.t("p.test"))
        table.add_column("", justify="right", width=10)
        for label, value, colour in [
            (self.t("p.tests_passed"), run.passed, PASS),
            (self.t("p.tests_failed"), run.failed, FAIL),
            ("ERROR", run.errors, FAIL),
            (self.t("p.tests_skipped"), run.skipped, SKIP),
            ("TOTAL", run.total, CREAM),
        ]:
            table.add_row(Text(label, style=colour), Text(str(value), style=f"bold {colour}"))

        meta = charts.kv_table(
            [
                (self.t("p.command"), Text(run.command or "—", style=CREAM)),
                (self.t("p.duration"), Text(f"{run.duration_seconds:.2f}s")),
                ("exit code", Text(str(run.exit_code), style=PASS if run.exit_code == 0 else FAIL)),
                (self.t("p.framework"), Text(f"{run.ecosystem.value} · {run.framework.value}")),
            ]
        )

        widgets: list[Widget] = [
            _heading(self.t("f.results")),
            Static(
                charts.stacked_bar(
                    [(run.passed, PASS), (run.failed + run.errors, FAIL), (run.skipped, SKIP)], 60
                )
            ),
            Static(table),
            Static(meta),
        ]
        if not run.has_executed:
            widgets.append(_text(self.t("p.run_first"), SKIP))
        return widgets

    def panel_gaps(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.gaps")), *self._needs_data()]
        gaps = audit.project.test_gaps
        if not gaps:
            return [_heading(self.t("f.gaps")), _text(self.t("p.no_gaps"), PASS)]

        table = Table(expand=True, border_style=MUTED, header_style=f"bold {CREAM}")
        table.add_column(self.t("p.priority"), width=8)
        table.add_column(self.t("p.file"), ratio=2, overflow="fold")
        table.add_column(self.t("p.functions"), ratio=2, overflow="fold")
        table.add_column(self.t("p.reason"), ratio=2, overflow="fold")
        for gap in gaps[:120]:
            colour = PRIORITY_COLOURS.get(gap.priority.value, MUTED)
            table.add_row(
                Text(gap.priority.value, style=f"bold {colour}"),
                Text(gap.source_module, style=CREAM),
                Text(", ".join(gap.functions_to_test[:5]) or "—", style=MUTED),
                Text(gap.reason, style=MUTED),
            )
        summary = Text()
        for level in ("HIGH", "MEDIUM", "LOW"):
            count = sum(1 for g in gaps if g.priority.value == level)
            summary.append(f"{level} {count}   ", style=PRIORITY_COLOURS[level])
        return [_heading(self.t("f.gaps"), f"{len(gaps)} total"), Static(summary), Static(table)]

    def panel_failures(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.failures")), *self._needs_data()]
        failures = audit.test_run.failures
        if not failures:
            return [_heading(self.t("f.failures")), _text(self.t("p.no_failures"), PASS)]

        widgets: list[Widget] = [_heading(self.t("f.failures"), f"{len(failures)} total")]
        for failure in failures[:40]:
            body = charts.kv_table(
                [
                    (
                        self.t("p.file"),
                        Text(f"{failure.file_path}:{failure.line_number or '?'}", style=CREAM),
                    ),
                    (self.t("p.error"), Text(f"{failure.error_type}: {failure.message}", style=FAIL)),
                    (self.t("p.suggestion"), Text(failure.suggested_fix or "—", style=PASS)),
                ]
            )
            widgets.append(Static(charts.section(failure.test_name, body, border=FAIL)))
        return widgets

    def panel_modules(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.modules")), *self._needs_data()]
        project = audit.project
        tested = {gap.source_module for gap in project.test_gaps}

        table = Table(expand=True, border_style=MUTED, header_style=f"bold {CREAM}")
        table.add_column("", width=2)
        table.add_column(self.t("p.file"), ratio=3, overflow="fold")
        table.add_column("lines", justify="right", width=7)
        table.add_column("fn", justify="right", width=5)
        table.add_column("cls", justify="right", width=5)
        for module in project.source_modules[:200]:
            covered = module.rel_path not in tested
            table.add_row(
                Text("✓" if covered else "◌", style=PASS if covered else MISS),
                Text(module.rel_path, style=CREAM if covered else MUTED),
                Text(str(module.line_count)),
                Text(str(len(module.functions))),
                Text(str(len(module.classes))),
            )
        return [
            _heading(
                self.t("f.modules"), f"{project.total_source_files} source · {project.total_test_files} test"
            ),
            Static(table),
        ]

    def panel_coverage(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.coverage")), *self._needs_data()]
        project = audit.project
        uncovered = {gap.source_module for gap in project.test_gaps}

        grid = Text()
        for index, module in enumerate(project.source_modules):
            covered = module.rel_path not in uncovered
            grid.append("█ " if covered else "▒ ", style=PASS if covered else MISS)
            if (index + 1) % 40 == 0:
                grid.append("\n")

        legend = Text()
        legend.append("█ ", style=PASS)
        legend.append("tested   ", style=MUTED)
        legend.append("▒ ", style=MISS)
        legend.append("missing", style=MUTED)

        return [
            _heading(self.t("f.coverage")),
            Static(charts.gauge(project.readiness_score, 50, self.t("p.readiness"))),
            Static(charts.section(self.t("p.distribution"), Group(grid, Text(""), legend))),
        ]

    def panel_history(self) -> list[Widget]:
        workspace = self.workspace
        history = [h for h in (workspace.history if workspace else []) if h.has_data]
        if not history:
            return [_heading(self.t("f.history")), *self._needs_data()]

        table = Table(expand=True, border_style=MUTED, header_style=f"bold {CREAM}")
        table.add_column("#", width=4, justify="right")
        table.add_column("timestamp")
        table.add_column(self.t("p.tests_passed"), justify="right")
        table.add_column(self.t("p.tests_failed"), justify="right")
        table.add_column(self.t("p.tests_missing"), justify="right")
        table.add_column(self.t("p.readiness"), justify="right")
        for index, snapshot in enumerate(reversed(history[-30:]), start=1):
            table.add_row(
                str(index),
                Text(snapshot.timestamp.replace("T", " ").replace("+00:00", ""), style=MUTED),
                Text(str(snapshot.passed), style=PASS),
                Text(str(snapshot.failed), style=FAIL if snapshot.failed else MUTED),
                Text(str(snapshot.missing), style=MISS),
                Text(f"{snapshot.readiness:.0f}%", style=CREAM),
            )
        return [
            _heading(self.t("f.history"), f"{len(history)} runs"),
            Static(charts.history_chart(history)),
            Static(table),
        ]

    # -- prompt ----------------------------------------------------------- #

    def _prompt_text(self) -> str:
        audit = self.audit
        if audit is None:
            return ""
        variant = self.screen.timmy.prompt_variant
        if variant == "failures":
            failures = audit.test_run.failures
            if not failures:
                return audit.agent_prompt
            lines = [f"# {audit.project.project_name} — failing tests", ""]
            for failure in failures:
                lines.append(f"## {failure.test_name}")
                lines.append(f"file: {failure.file_path}:{failure.line_number or '?'}")
                lines.append(f"error: {failure.error_type}: {failure.message}")
                if failure.suggested_fix:
                    lines.append(f"hint: {failure.suggested_fix}")
                lines.append("")
            return "\n".join(lines)
        if variant == "gaps":
            gaps = audit.project.test_gaps
            lines = [f"# {audit.project.project_name} — missing tests", ""]
            for gap in gaps:
                lines.append(f"- [{gap.priority.value}] {gap.source_module} -> {gap.suggested_test_file}")
                if gap.functions_to_test:
                    lines.append(f"  functions: {', '.join(gap.functions_to_test[:12])}")
            return "\n".join(lines)
        return audit.agent_prompt

    def panel_prompt_preview(self) -> list[Widget]:
        prompt = self._prompt_text()
        if not prompt:
            return [_heading(self.t("f.prompt_preview")), *self._needs_data()]
        return [
            _heading(self.t("f.prompt_preview"), f"{len(prompt)} chars · ~{len(prompt) // 4} tokens"),
            Static(Syntax(prompt, "markdown", theme="ansi_dark", word_wrap=True, background_color="default")),
        ]

    def panel_prompt_copy(self) -> list[Widget]:
        if self.audit is None:
            return [_heading(self.t("f.prompt_copy")), *self._needs_data()]
        return [
            _heading(self.t("f.prompt_copy"), self.t("p.tokens_desc")),
            Horizontal(
                Button(self.t("f.prompt_copy"), id="act-copy-prompt", variant="success"),
                classes="actions",
            ),
            Static(id="act-copy-status"),
        ]

    def panel_prompt_export(self) -> list[Widget]:
        if self.audit is None:
            return [_heading(self.t("f.prompt_export")), *self._needs_data()]
        default = str((self.workspace.root / "timmytest-prompt.md") if self.workspace else "prompt.md")
        return [
            _heading(self.t("f.prompt_export")),
            Input(value=default, id="act-export-path"),
            Horizontal(
                Button(self.t("f.prompt_export"), id="act-export-prompt", variant="success"),
                classes="actions",
            ),
            Static(id="act-export-status"),
        ]

    def panel_prompt_tokens(self) -> list[Widget]:
        audit = self.audit
        if audit is None:
            return [_heading(self.t("f.prompt_tokens")), *self._needs_data()]

        prompt_tokens = max(1, len(audit.agent_prompt) // 4)
        # What an agent would burn rediscovering the same surface by reading files.
        source_chars = sum(m.line_count for m in audit.project.source_modules) * 42
        test_chars = sum(m.line_count for m in audit.project.test_modules) * 42
        naive_tokens = max(prompt_tokens, (source_chars + test_chars) // 4)
        saved = max(0, naive_tokens - prompt_tokens)
        ratio = saved / naive_tokens * 100 if naive_tokens else 0

        tiles = charts.stat_row(
            [
                charts.stat_tile("PROMPT", f"{prompt_tokens // 1000}", ACCENT, "k tokens"),
                charts.stat_tile("NAIVE", f"{naive_tokens // 1000}", SKIP, "k tokens"),
                charts.stat_tile("SAVED", f"{saved // 1000}", PASS, "k tokens"),
            ]
        )
        return [
            _heading(self.t("f.prompt_tokens"), self.t("p.tokens_desc")),
            Static(tiles, classes="tiles"),
            Static(charts.gauge(ratio, 46, self.t("p.tokens_saved"))),
        ]

    def panel_prompt_style(self) -> list[Widget]:
        current = self.screen.timmy.prompt_variant
        widgets: list[Widget] = [_heading(self.t("f.prompt_style"))]
        for key, label in PROMPT_VARIANTS:
            widgets.append(Checkbox(label, value=key == current, id=f"variant-{key}", classes="variant-box"))
        widgets.append(Static(id="act-variant-status"))
        return widgets

    # -- discord ---------------------------------------------------------- #

    def _discord_message(self) -> str:
        audit = self.audit
        workspace = self.workspace
        if audit is None or workspace is None:
            return ""
        passed, failed, skipped, missing = self.counts()
        status = "❌ FAIL" if failed else "✅ PASS"
        return (
            f"**TimmyTest — {workspace.name}** {status}\n"
            f"passed `{passed}` · failed `{failed}` · skipped `{skipped}` · missing tests `{missing}`\n"
            f"readiness `{audit.project.readiness_score:.1f}%` · "
            f"{audit.project.ecosystem.value}/{audit.project.test_framework.value}\n"
            f"`{audit.test_run.command}`"
        )

    def panel_discord_webhook(self) -> list[Widget]:
        workspace = self.workspace
        return [
            _heading(self.t("f.discord_webhook"), "https://discord.com/api/webhooks/…"),
            Input(
                value=workspace.webhook if workspace else "",
                placeholder="https://discord.com/api/webhooks/…",
                password=True,
                id="act-webhook-input",
            ),
            Horizontal(
                Button(self.t("p.save"), id="act-webhook-save", variant="success"),
                classes="actions",
            ),
            Static(id="act-webhook-status"),
        ]

    def panel_discord_send(self) -> list[Widget]:
        workspace = self.workspace
        if self.audit is None:
            return [_heading(self.t("f.discord_send")), *self._needs_data()]
        if not (workspace and workspace.webhook):
            return [_heading(self.t("f.discord_send")), _text(self.t("p.webhook_missing"), SKIP)]
        return [
            _heading(self.t("f.discord_send"), self.t("p.confirm_send")),
            Static(charts.section("preview", Text(self._discord_message(), style=CREAM))),
            Horizontal(
                Button(self.t("p.send"), id="act-discord-send", variant="success"),
                classes="actions",
            ),
            Static(id="act-discord-status"),
        ]

    def panel_discord_rules(self) -> list[Widget]:
        workspace = self.workspace
        if workspace is None:
            return [_heading(self.t("f.discord_rules")), *self._needs_data()]
        return [
            _heading(self.t("f.discord_rules")),
            Checkbox(self.t("p.tests_failed"), value=workspace.notify_on_fail, id="rule-fail"),
            Checkbox(self.t("p.tests_passed"), value=workspace.notify_on_pass, id="rule-pass"),
            Checkbox(self.t("p.tests_missing"), value=workspace.notify_on_gaps, id="rule-gaps"),
            Static(id="act-rules-status"),
        ]

    def panel_discord_preview(self) -> list[Widget]:
        message = self._discord_message()
        if not message:
            return [_heading(self.t("f.discord_preview")), *self._needs_data()]
        payload = json.dumps({"content": message}, indent=2, ensure_ascii=False)
        return [
            _heading(self.t("f.discord_preview")),
            Static(Syntax(payload, "json", theme="ansi_dark", word_wrap=True, background_color="default")),
        ]

    def panel_discord_status(self) -> list[Widget]:
        workspace = self.workspace
        configured = bool(workspace and workspace.webhook)
        rows: list[tuple[str, RenderableType]] = [
            (
                "webhook",
                Text("configured" if configured else "not configured", style=PASS if configured else MUTED),
            ),
            (
                "rules",
                Text(
                    ", ".join(
                        name
                        for name, on in [
                            ("fail", workspace.notify_on_fail if workspace else False),
                            ("pass", workspace.notify_on_pass if workspace else False),
                            ("gaps", workspace.notify_on_gaps if workspace else False),
                        ]
                        if on
                    )
                    or "—",
                    style=CREAM,
                ),
            ),
            ("last send", Text(self.screen.timmy.last_discord_result or "—", style=MUTED)),
        ]
        return [_heading(self.t("f.discord_status")), Static(charts.kv_table(rows))]

    # -- agent integrations ------------------------------------------------ #

    _INTEGRATIONS = {
        "agents_claude": ("claude", "CLAUDE.md"),
        "agents_cursor": ("cursor", ".cursorrules · .cursor/rules/"),
        "agents_copilot": ("copilot", ".github/copilot-instructions.md"),
        "agents_universal": ("agents", "AGENTS.md"),
        "agents_mcp": ("mcp", ".cursor/mcp.json"),
        "agents_ci": ("ci", ".github/workflows/timmytest.yml"),
    }

    def _integration_panel(self, feature_key: str) -> list[Widget]:
        flag, files = self._INTEGRATIONS[feature_key]
        workspace = self.workspace
        if workspace is None:
            return [_heading(self.t(f"f.{feature_key}")), *self._needs_data()]
        return [
            _heading(self.t(f"f.{feature_key}"), files),
            Static(
                charts.kv_table(
                    [
                        ("target", Text(str(workspace.root), style=CREAM)),
                        ("writes", Text(files, style=ACCENT)),
                    ]
                )
            ),
            Horizontal(
                Button(self.t("p.apply"), id=f"act-integrate-{flag}", variant="success"),
                classes="actions",
            ),
            Static(id="act-integrate-status"),
        ]

    def panel_agents_claude(self) -> list[Widget]:
        return self._integration_panel("agents_claude")

    def panel_agents_cursor(self) -> list[Widget]:
        return self._integration_panel("agents_cursor")

    def panel_agents_copilot(self) -> list[Widget]:
        return self._integration_panel("agents_copilot")

    def panel_agents_universal(self) -> list[Widget]:
        return self._integration_panel("agents_universal")

    def panel_agents_mcp(self) -> list[Widget]:
        widgets = self._integration_panel("agents_mcp")
        widgets.insert(
            2,
            Static(
                charts.section(
                    "stdio",
                    Text("timmytest mcp", style=CREAM),
                )
            ),
        )
        return widgets

    def panel_agents_ci(self) -> list[Widget]:
        return self._integration_panel("agents_ci")

    # -- tools ------------------------------------------------------------ #

    def panel_tools_scaffold(self) -> list[Widget]:
        if self.audit is None:
            return [_heading(self.t("f.tools_scaffold")), *self._needs_data()]
        gaps = self.audit.project.test_gaps
        return [
            _heading(self.t("f.tools_scaffold"), f"{len(gaps)} {self.t('p.tests_missing').lower()}"),
            Horizontal(
                Button(self.t("p.apply"), id="act-scaffold", variant="success"),
                classes="actions",
            ),
            Static(id="act-scaffold-status"),
        ]

    def panel_tools_config(self) -> list[Widget]:
        workspace = self.workspace
        if workspace is None:
            return [_heading(self.t("f.tools_config")), *self._needs_data()]
        config = load_project_config(workspace.root)
        rows: list[tuple[str, RenderableType]] = [
            (key, Text(str(value), style=CREAM)) for key, value in config.model_dump().items()
        ]
        candidates = [".timmytest.yml", ".timmytest.yaml", "timmytest.toml", "pyproject.toml"]
        found = [name for name in candidates if (workspace.root / name).is_file()]
        return [
            _heading(self.t("f.tools_config"), ", ".join(found) or "defaults"),
            Static(charts.kv_table(rows)),
        ]

    def panel_tools_report(self) -> list[Widget]:
        if self.audit is None:
            return [_heading(self.t("f.tools_report")), *self._needs_data()]
        default = str((self.workspace.root / "timmytest-report.md") if self.workspace else "report.md")
        return [
            _heading(self.t("f.tools_report")),
            Input(value=default, id="act-report-path"),
            Horizontal(
                Button(self.t("p.save"), id="act-export-report", variant="success"), classes="actions"
            ),
            Static(id="act-report-status"),
        ]

    def panel_tools_json(self) -> list[Widget]:
        if self.audit is None:
            return [_heading(self.t("f.tools_json")), *self._needs_data()]
        default = str((self.workspace.root / "timmytest-audit.json") if self.workspace else "audit.json")
        return [
            _heading(self.t("f.tools_json")),
            Input(value=default, id="act-json-path"),
            Horizontal(Button(self.t("p.save"), id="act-export-json", variant="success"), classes="actions"),
            Static(id="act-json-status"),
        ]

    def panel_tools_log(self) -> list[Widget]:
        log = self.screen.timmy.activity
        if not log:
            return [_heading(self.t("f.tools_log")), _text("—", MUTED)]
        text = Text()
        for entry in reversed(log[-200:]):
            text.append(f"{entry}\n", style=MUTED)
        return [_heading(self.t("f.tools_log"), f"{len(log)} entries"), Static(text)]

    # -- settings ---------------------------------------------------------- #

    def panel_settings_language(self) -> list[Widget]:
        return [
            _heading(self.t("f.settings_language")),
            Horizontal(
                Button(
                    "Türkçe", id="act-lang-tr", variant="primary" if self.t.language == "tr" else "default"
                ),
                Button(
                    "English", id="act-lang-en", variant="primary" if self.t.language == "en" else "default"
                ),
                classes="actions",
            ),
            Static(id="act-lang-status"),
        ]

    def panel_settings_workspaces(self) -> list[Widget]:
        state = self.screen.state
        widgets: list[Widget] = [_heading(self.t("f.settings_workspaces"), f"{len(state.workspaces)} total")]
        vendor_names = dict(AI_VENDORS)
        for workspace in state.workspaces:
            active = workspace.id == state.active_workspace
            body = charts.kv_table(
                [
                    ("path", Text(workspace.path, style=CREAM)),
                    ("vendors", Text(", ".join(vendor_names.get(v, v) for v in workspace.vendors) or "—")),
                    ("created", Text(workspace.created_at.replace("T", " "), style=MUTED)),
                    (
                        self.t("dash.last_run"),
                        Text(
                            workspace.last_run.timestamp.replace("T", " ") or self.t("dash.never_run"),
                            style=MUTED,
                        ),
                    ),
                ]
            )
            widgets.append(
                Static(
                    charts.section(
                        f"{'● ' if active else ''}{workspace.name}",
                        body,
                        border=PASS if active else MUTED,
                    )
                )
            )
            widgets.append(
                Horizontal(
                    Button(self.t("p.switch"), id=f"act-ws-switch-{workspace.id}", disabled=active),
                    Button(self.t("p.remove"), id=f"act-ws-remove-{workspace.id}", variant="error"),
                    classes="actions",
                )
            )
        widgets.append(
            Horizontal(Button(self.t("ws.create"), id="act-ws-new", variant="success"), classes="actions")
        )
        widgets.append(Static(id="act-ws-status"))
        return widgets

    def panel_settings_about(self) -> list[Widget]:
        from timmytest.tui.features import enabled_features

        feature_count = sum(len(group.features) for group in GROUPS)
        active_count = len(enabled_features())
        rows: list[tuple[str, RenderableType]] = [
            (self.t("p.version"), Text(__version__, style=CREAM)),
            (self.t("p.state_file"), Text(str(STATE_FILE), style=MUTED)),
            ("features", Text(f"{active_count}/{feature_count}", style=ACCENT)),
            ("workspaces", Text(str(len(self.screen.state.workspaces)), style=ACCENT)),
        ]
        return [
            _heading("TimmyTest", self.t("p.about_desc")),
            Static(charts.kv_table(rows)),
        ]


def resolve_export_path(raw: str, fallback: Path) -> Path:
    text = raw.strip().strip("\"'")
    return Path(text).expanduser() if text else fallback
