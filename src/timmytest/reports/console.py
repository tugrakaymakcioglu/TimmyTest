"""Rich terminal reports and formatting for TimmyTest."""

import contextlib
import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from timmytest.detector.models import CoverageReport, Priority, ProjectInfo, TestRunResult

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

#: Terminal tables are for triage, not for archives - the full list lives in the
#: JSON export and the Markdown report.
MAX_CONSOLE_GAPS = 40


def print_project_summary(project: ProjectInfo) -> None:
    """Print the detected project summary table."""
    table = Table(title="📦 Project Overview", show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Property", style="bold white", width=22)
    table.add_column("Value", style="green")

    table.add_row("Project Name", project.project_name)
    table.add_row("Ecosystem", project.ecosystem.value.upper())
    table.add_row("Test Framework", project.test_framework.value.upper())
    table.add_row("Config Files", ", ".join(project.config_files) or "None detected")
    table.add_row("Recommended Command", project.test_command or "None")
    table.add_row("Source Modules", str(len(project.source_modules)))
    table.add_row("Existing Test Files", str(len(project.test_modules)))

    # Readiness Score with color
    score = project.readiness_score
    score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")
    table.add_row("Test Readiness Score", f"[{score_color}]{score}%[/{score_color}]")

    console.print(table)
    console.print("")


def print_test_run_summary(test_run: TestRunResult) -> None:
    """Print the test execution summary."""
    if not test_run.has_executed:
        return

    table = Table(title="⚡ Test Execution Results", show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Metric", style="bold white", width=22)
    table.add_column("Result", style="white")

    total_color = "white"
    pass_color = "green" if test_run.passed > 0 else "white"
    fail_color = "bold red" if test_run.failed > 0 else "dim green"
    error_color = "bold red" if test_run.errors > 0 else "dim green"
    skip_color = "yellow" if test_run.skipped > 0 else "dim white"

    table.add_row("Total Tests", f"[{total_color}]{test_run.total}[/{total_color}]")
    table.add_row("Passed", f"[{pass_color}]{test_run.passed}[/{pass_color}]")
    table.add_row("Failed", f"[{fail_color}]{test_run.failed}[/{fail_color}]")
    # Suites that never loaded (collection/import errors) are not test failures
    # but still make the run untrustworthy, so they get their own line.
    table.add_row("Errors (suite/setup)", f"[{error_color}]{test_run.errors}[/{error_color}]")
    table.add_row("Skipped / Ignored", f"[{skip_color}]{test_run.skipped}[/{skip_color}]")
    table.add_row("Duration", f"{test_run.duration_seconds}s")
    table.add_row("Exit Code", f"{test_run.exit_code}")
    table.add_row("Executed Command", f"[dim cyan]{test_run.command}[/dim cyan]")

    console.print(table)
    console.print("")


def print_failures(test_run: TestRunResult) -> None:
    """Print detailed failure diagnostics and suggestions."""
    if not test_run.failures:
        if test_run.has_executed and test_run.failed == 0 and test_run.errors == 0:
            console.print(
                Panel(
                    "[bold green]✨ All executed tests passed cleanly! No test failures detected.[/bold green]",
                    border_style="green",
                    padding=(0, 2),
                )
            )
            console.print("")
        return

    console.print(f"[bold red]❌ Failed Tests ({len(test_run.failures)}):[/bold red]")

    for idx, failure in enumerate(test_run.failures, start=1):
        loc = (
            f" in [underline cyan]{failure.file_path}:{failure.line_number}[/underline cyan]"
            if failure.file_path
            else ""
        )
        content = (
            f"[bold red]{idx}. {failure.test_name}[/bold red]{loc}\n\n"
            f"[bold white]Error Type:[/bold white] [yellow]{failure.error_type}[/yellow]\n"
            f"[bold white]Message:[/bold white] {failure.message}\n"
        )

        if failure.suggested_fix:
            content += f"\n[bold green]💡 Timmy Suggestion:[/bold green] [bold cyan]{failure.suggested_fix}[/bold cyan]"

        if failure.traceback:
            content += f"\n\n[dim white]Traceback excerpt:\n{failure.traceback}[/dim white]"

        console.print(
            Panel(
                content,
                border_style="red",
                padding=(0, 2),
            )
        )
    console.print("")


def print_coverage_summary(coverage: CoverageReport) -> None:
    """Print a coverage report summary with the worst-covered files."""
    score_color = (
        "green" if coverage.total_percent >= 80 else ("yellow" if coverage.total_percent >= 50 else "red")
    )

    table = Table(
        title=f"🧪 Test Coverage ({coverage.source})",
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Metric", style="bold white", width=20)
    table.add_column("Value", style="white")
    table.add_row("Overall Line Coverage", f"[{score_color}]{coverage.total_percent}%[/{score_color}]")
    table.add_row("Files Tracked", str(len(coverage.files)))
    console.print(table)
    console.print("")

    # Show the lowest-covered files to focus remediation.
    worst = sorted(coverage.files, key=lambda f: f.percent)[:10]
    if worst:
        wt = Table(title="📉 Lowest-Covered Files", show_header=True, header_style="bold red", expand=False)
        wt.add_column("File", style="cyan", width=45)
        wt.add_column("Coverage", style="bold white", width=12)
        for f in worst:
            c = "red" if f.percent < 50 else "yellow"
            wt.add_row(f.path, f"[{c}]{f.percent}%[/{c}]")
        console.print(wt)
        console.print("")


def print_test_gaps(project: ProjectInfo) -> None:
    """Print missing test modules table."""
    if not project.test_gaps:
        console.print(
            Panel(
                "[bold green]🎯 Full Coverage Readiness: All discovered source modules have matching test files.[/bold green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        console.print("")
        return

    table = Table(
        title=f"⚠️ Missing Test Modules & Test Gaps ({len(project.test_gaps)})",
        show_header=True,
        header_style="bold yellow",
        expand=False,
    )
    table.add_column("Priority", style="bold", width=12)
    table.add_column("Untested Source Module", style="cyan", width=35)
    table.add_column("Suggested Test File", style="green", width=35)
    table.add_column("Reason / Coverage Target", style="white")

    for gap in project.test_gaps[:MAX_CONSOLE_GAPS]:
        p_style = (
            "bold red"
            if gap.priority == Priority.HIGH
            else ("bold yellow" if gap.priority == Priority.MEDIUM else "blue")
        )
        table.add_row(
            f"[{p_style}]{gap.priority.value}[/{p_style}]",
            gap.source_module,
            gap.suggested_test_file,
            gap.reason,
        )

    console.print(table)
    # Gaps are sorted highest-priority first, so the truncated tail is the least
    # urgent work. Scrolling 200+ rows off the top of the terminal helped nobody.
    hidden = len(project.test_gaps) - MAX_CONSOLE_GAPS
    if hidden > 0:
        console.print(
            f"[dim]… and {hidden} more, lowest priority last. "
            f"Use --json or --save-report for the complete list.[/dim]"
        )
    console.print("")


def print_prompt_panel(prompt_text: str, copied: bool = False) -> None:
    """Print the AI agent prompt formatted panel."""
    copied_badge = " [bold green]✓ COPIED TO CLIPBOARD[/bold green]" if copied else ""
    console.print(f"[bold cyan]🤖 AI Agent Handoff Prompt[/bold cyan]{copied_badge}")

    syntax = Syntax(prompt_text, "markdown", theme="monokai", line_numbers=False, word_wrap=True)
    console.print(
        Panel(
            syntax,
            title="[bold white]Copy & Paste this directly to Claude Code / Codex / Antigravity / Cursor[/bold white]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print("")
