"""TimmyTest CLI entrypoint with CI exit code propagation, watch mode, and configuration support."""

import contextlib
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

# Reconfigure stdout/stderr for Windows console compatibility (e.g. cp1254 / cp1252)
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from timmytest import __version__, flags
from timmytest.analysis import analyze_project as _analyze_project
from timmytest.banner import print_banner, show_fullscreen_splash
from timmytest.config import TimmyConfig, load_project_config
from timmytest.detector.models import ProjectAudit
from timmytest.integrations.installer import integrate_project
from timmytest.mcp.server import run_mcp_server
from timmytest.prompt.clipboard import copy_to_clipboard
from timmytest.reports.console import (
    console,
    print_coverage_summary,
    print_failures,
    print_project_summary,
    print_prompt_panel,
    print_test_gaps,
    print_test_run_summary,
)
from timmytest.reports.json_export import export_audit_to_json
from timmytest.scaffolder.init_tests import initialize_test_scaffold
from timmytest.walk import IGNORED_DIRS, iter_files

app = typer.Typer(
    name="timmytest",
    help="⚡ Zero-token terminal test runner, test-gap analyzer, and AI agent prompt generator.",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
    no_splash: Annotated[
        bool,
        typer.Option("--no-splash", help="Skip animated splash screen"),
    ] = False,
    classic: Annotated[
        bool,
        typer.Option("--classic", help="Print the command list instead of launching the app"),
    ] = False,
) -> None:
    """
    ⚡ Zero-token terminal test runner, test-gap analyzer, and AI agent prompt generator.
    """
    if ctx.invoked_subcommand is None:
        # Bare `timmytest` opens the full-screen application, but only when a real
        # terminal is attached - piped output and CI keep the classic command list.
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if not classic and interactive and flags.is_enabled("cli.ui"):
            from timmytest.tui.app import launch

            launch()
            raise typer.Exit()

        if not no_banner:
            if not no_splash:
                show_fullscreen_splash(animate_progress=True)
            else:
                print_banner()
        console.print("[bold cyan]Commands:[/bold cyan]")
        console.print(
            "  [bold green]check[/bold green]      Run test suite, analyze failures & gap diagnostics, generate AI prompts"
        )
        console.print(
            "  [bold green]scan[/bold green]       Fast test-gap scanner without executing test suites"
        )
        console.print(
            "  [bold green]run[/bold green]        Run tests with live feedback & CI error exit code propagation"
        )
        console.print(
            "  [bold green]prompt[/bold green]     Extract failures and generate prompt directly for Claude / Cursor / AGY"
        )
        console.print("  [bold green]init[/bold green]       Scaffold missing test files automatically")
        console.print(
            "  [bold green]integrate[/bold green]  Configure repository with agent rules & MCP configs"
        )
        console.print("  [bold green]agent[/bold green]      Direct zero-noise output for AI coding agents")
        console.print("  [bold green]ui[/bold green]         Launch the full-screen TimmyTest application")
        console.print("  [bold green]mcp[/bold green]        Start the Model Context Protocol (MCP) server\n")
        console.print("[dim]Run [bold]timmytest COMMAND --help[/bold] for detailed command options.[/dim]\n")
        raise typer.Exit()


def _require(feature_key: str) -> None:
    """Abort the command when its switch is off in the TimmyTestDev panel."""
    if flags.is_enabled(feature_key):
        return
    source = flags.source_path()
    console.print(f"[bold yellow]⛔ '{feature_key}' is switched off for this install.[/bold yellow]")
    if source is not None:
        console.print(f"[dim]Switch file: {source}[/dim]")
    raise typer.Exit(code=2)


def _get_project_mtimes(root: Path, config: TimmyConfig) -> dict[str, float]:
    """Get modification timestamps of all tracked project files.

    Watch mode re-runs this every ``watch_interval`` seconds. Previously it only
    skipped the user's own ``ignored_dirs`` (empty by default), so each tick
    stat'ed the entire dependency tree - tens of thousands of files a second on
    a normal Node project, for a poll that should be nearly free.
    """
    mtimes: dict[str, float] = {}
    ignored = set(IGNORED_DIRS) | set(config.ignored_dirs)
    for path in iter_files(root, ignored):
        with contextlib.suppress(OSError):
            mtimes[str(path)] = path.stat().st_mtime
    return mtimes


def _write_output(target: Path, content: str, label: str) -> None:
    """Write a generated artefact, creating its directory and reporting failure.

    ``--save-report reports/audit.md`` used to raise a raw traceback when the
    directory did not exist, after the whole audit had already been paid for.
    """
    try:
        if target.parent != Path():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        console.print(f"[bold red]✗ Could not save {label}:[/bold red] {exc.strerror or exc}")
        return
    console.print(f"[bold green]✓ {label} saved to:[/bold green] {target}")


def _failing_count(audit: ProjectAudit) -> int:
    """Failures that must break CI: assertion failures *and* suite/collection errors.

    Counting only ``failed`` let a suite that never loaded - every test in it
    green, exit code 1 - pass a pipeline silently.
    """
    return audit.test_run.failed + audit.test_run.errors


@app.command(name="check")
def check_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    copy_prompt_flag: Annotated[
        bool,
        typer.Option("--copy-prompt/--no-copy-prompt", "-c/-nc", help="Copy AI agent prompt to clipboard"),
    ] = True,
    save_prompt: Annotated[
        Path | None,
        typer.Option("--save-prompt", "-sp", help="File path to save the generated AI agent prompt"),
    ] = None,
    save_report: Annotated[
        Path | None,
        typer.Option("--save-report", "-sr", help="File path to save the Markdown audit report"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output audit results in JSON format"),
    ] = False,
    timeout: Annotated[
        int | None,
        typer.Option(
            "--timeout",
            "-t",
            help="Test execution timeout in seconds (default: 60, or timeout_seconds from config)",
        ),
    ] = None,
    filter_pattern: Annotated[
        str | None,
        typer.Option("--filter", "-k", help="Filter tests by name pattern"),
    ] = None,
    cmd: Annotated[
        str | None,
        typer.Option("--cmd", help="Custom test command to execute"),
    ] = None,
    no_run: Annotated[
        bool,
        typer.Option("--no-run", help="Skip running tests (static gap analysis only)"),
    ] = False,
    safe_dry_run: Annotated[
        bool,
        typer.Option(
            "--safe", "--dry-run", help="Safe mode: analyze without running tests on untrusted code"
        ),
    ] = False,
    fail_under: Annotated[
        float | None,
        typer.Option("--fail-under", help="Minimum required test readiness score percentage (0-100)"),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch for file changes and continuously re-audit"),
    ] = False,
    changed: Annotated[
        bool,
        typer.Option("--changed", help="Run only tests affected by uncommitted changes (vs HEAD)"),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since", help="Run only tests affected by changes since a git ref (e.g. HEAD~1, main)"
        ),
    ] = None,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            help="Enable coverage-aware analysis (auto-detects coverage.json/cobertura.xml/lcov.info)",
        ),
    ] = False,
    coverage_file: Annotated[
        Path | None,
        typer.Option("--coverage-file", help="Explicit coverage report path"),
    ] = None,
    coverage_threshold: Annotated[
        float,
        typer.Option("--coverage-threshold", help="Minimum line coverage %% to flag low-coverage files"),
    ] = 60.0,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Run complete audit: Scan modules, detect test gaps, run tests, diagnose failures, and generate AI prompt.
    """
    _require("cli.check")
    if not flags.is_enabled("core.coverage"):
        coverage, coverage_file = False, None
    watch = watch and flags.is_enabled("core.watch")
    config = load_project_config(path)
    # An explicit --timeout wins; otherwise the project's config does, and only
    # then the 60s default. Defaulting the option to 60 here would make
    # `timeout_seconds` in .timmytest.yml unreachable.
    effective_timeout = timeout if timeout is not None else config.timeout_seconds
    should_run = not (no_run or safe_dry_run)

    def _execute_single_audit() -> ProjectAudit:
        audit = _analyze_project(
            project_dir=path,
            custom_cmd=cmd,
            execute_tests=should_run,
            timeout_seconds=effective_timeout,
            filter_pattern=filter_pattern,
            config=config,
            coverage=coverage,
            coverage_path=coverage_file,
            coverage_threshold=coverage_threshold,
            changed=changed,
            since=since,
        )

        if json_output:
            typer.echo(export_audit_to_json(audit))
            return audit

        if not no_banner:
            print_banner()

        print_project_summary(audit.project)
        if audit.test_run.has_executed:
            print_test_run_summary(audit.test_run)
            print_failures(audit.test_run)
        print_test_gaps(audit.project)
        if audit.project.coverage is not None:
            print_coverage_summary(audit.project.coverage)

        copied = False
        if copy_prompt_flag and config.copy_prompt:
            copied = copy_to_clipboard(audit.agent_prompt)

        print_prompt_panel(audit.agent_prompt, copied=copied)

        if save_prompt:
            _write_output(save_prompt, audit.agent_prompt, "AI Agent Prompt")

        if save_report:
            _write_output(save_report, audit.summary_markdown, "Audit Report")

        return audit

    audit = _execute_single_audit()

    if watch:
        console.print("[bold cyan]👀 Watching for file changes... (Press Ctrl+C to exit)[/bold cyan]")
        last_mtimes = _get_project_mtimes(path.resolve(), config)
        try:
            while True:
                time.sleep(config.watch_interval)
                current_mtimes = _get_project_mtimes(path.resolve(), config)
                if current_mtimes != last_mtimes:
                    console.print(
                        "\n[bold yellow]🔄 File change detected. Re-running audit...[/bold yellow]\n"
                    )
                    _execute_single_audit()
                    last_mtimes = current_mtimes
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping watch mode.[/bold yellow]")
            return

    # CI/CD exit code checks
    target_score = fail_under if fail_under is not None else config.min_readiness_score
    if target_score > 0 and audit.project.readiness_score < target_score:
        console.print(
            f"[bold red]❌ Test readiness score ({audit.project.readiness_score}%) is below required threshold ({target_score}%).[/bold red]"
        )
        raise typer.Exit(code=1)

    if audit.test_run.has_executed and _failing_count(audit) > 0 and config.fail_on_test_failure:
        raise typer.Exit(code=1)


@app.command(name="scan")
def scan_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output scan results in JSON format"),
    ] = False,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            help="Enable coverage-aware analysis (auto-detects coverage.json/cobertura.xml/lcov.info)",
        ),
    ] = False,
    coverage_file: Annotated[
        Path | None,
        typer.Option("--coverage-file", help="Explicit coverage report path"),
    ] = None,
    coverage_threshold: Annotated[
        float,
        typer.Option("--coverage-threshold", help="Minimum line coverage %% to flag low-coverage files"),
    ] = 60.0,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    🔍 Fast static scan: Discover source modules, existing test files, and missing test gaps.
    """
    _require("cli.scan")
    if not flags.is_enabled("core.coverage"):
        coverage, coverage_file = False, None
    audit = _analyze_project(
        project_dir=path,
        execute_tests=False,
        coverage=coverage,
        coverage_path=coverage_file,
        coverage_threshold=coverage_threshold,
    )

    if json_output:
        typer.echo(export_audit_to_json(audit))
        return

    if not no_banner:
        print_banner()

    print_project_summary(audit.project)
    print_test_gaps(audit.project)
    if audit.project.coverage is not None:
        print_coverage_summary(audit.project.coverage)


@app.command(name="run")
def run_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    timeout: Annotated[
        int | None,
        typer.Option(
            "--timeout",
            "-t",
            help="Test execution timeout in seconds (default: 60, or timeout_seconds from config)",
        ),
    ] = None,
    filter_pattern: Annotated[
        str | None,
        typer.Option("--filter", "-k", help="Filter tests by name pattern"),
    ] = None,
    cmd: Annotated[
        str | None,
        typer.Option("--cmd", help="Custom test command to execute"),
    ] = None,
    only_failures: Annotated[
        bool,
        typer.Option("--only-failures", "-f", help="Show only failure diagnostics and suggestions"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output execution results in JSON format"),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch for file changes and continuously re-run tests"),
    ] = False,
    changed: Annotated[
        bool,
        typer.Option("--changed", help="Run only tests affected by uncommitted changes (vs HEAD)"),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since", help="Run only tests affected by changes since a git ref (e.g. HEAD~1, main)"
        ),
    ] = None,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            help="Enable coverage-aware analysis (auto-detects coverage.json/cobertura.xml/lcov.info)",
        ),
    ] = False,
    coverage_file: Annotated[
        Path | None,
        typer.Option("--coverage-file", help="Explicit coverage report path"),
    ] = None,
    coverage_threshold: Annotated[
        float,
        typer.Option("--coverage-threshold", help="Minimum line coverage %% to flag low-coverage files"),
    ] = 60.0,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Execute tests, parse PASS/FAIL results, and display rich failure diagnostics & fix suggestions.
    """
    _require("cli.run")
    if not flags.is_enabled("core.coverage"):
        coverage, coverage_file = False, None
    watch = watch and flags.is_enabled("core.watch")
    config = load_project_config(path)
    effective_timeout = timeout if timeout is not None else config.timeout_seconds

    def _execute_run() -> ProjectAudit:
        audit = _analyze_project(
            project_dir=path,
            custom_cmd=cmd,
            execute_tests=True,
            timeout_seconds=effective_timeout,
            filter_pattern=filter_pattern,
            config=config,
            coverage=coverage,
            coverage_path=coverage_file,
            coverage_threshold=coverage_threshold,
            changed=changed,
            since=since,
        )

        if json_output:
            typer.echo(export_audit_to_json(audit))
            return audit

        if not no_banner:
            print_banner()

        if not only_failures:
            print_project_summary(audit.project)
            print_test_run_summary(audit.test_run)
            if audit.project.coverage is not None:
                print_coverage_summary(audit.project.coverage)

        print_failures(audit.test_run)
        return audit

    audit = _execute_run()

    if watch:
        console.print("[bold cyan]👀 Watching for file changes... (Press Ctrl+C to exit)[/bold cyan]")
        last_mtimes = _get_project_mtimes(path.resolve(), config)
        try:
            while True:
                time.sleep(config.watch_interval)
                current_mtimes = _get_project_mtimes(path.resolve(), config)
                if current_mtimes != last_mtimes:
                    console.print(
                        "\n[bold yellow]🔄 File change detected. Re-running tests...[/bold yellow]\n"
                    )
                    _execute_run()
                    last_mtimes = current_mtimes
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping watch mode.[/bold yellow]")
            return

    if audit.test_run.has_executed and _failing_count(audit) > 0 and config.fail_on_test_failure:
        raise typer.Exit(code=1)


@app.command(name="prompt")
def prompt_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    copy_flag: Annotated[
        bool,
        typer.Option("--copy/--no-copy", "-c/-nc", help="Copy generated prompt to clipboard"),
    ] = True,
    output_file: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="File to write the prompt into"),
    ] = None,
    no_run: Annotated[
        bool,
        typer.Option("--no-run", help="Generate prompt from static scan only"),
    ] = False,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Output raw prompt text without TUI panel"),
    ] = False,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner (kept for CLI consistency)"),
    ] = False,
) -> None:
    """
    🤖 Generate an ultra-dense, token-optimized prompt for AI coding agents.
    """
    _require("cli.prompt")
    audit = _analyze_project(project_dir=path, execute_tests=not no_run)

    copied = False
    if copy_flag:
        copied = copy_to_clipboard(audit.agent_prompt)

    if output_file:
        # Mirror check/--save-prompt: writing into a not-yet-existing directory
        # must create it, not crash after the whole audit has been paid for.
        if output_file.parent != Path():
            with contextlib.suppress(OSError):
                output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_file.write_text(audit.agent_prompt, encoding="utf-8")
        except OSError as exc:
            console.print(f"[bold red]✗ Could not write prompt:[/bold red] {exc.strerror or exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"[bold green]✓ Prompt written to:[/bold green] {output_file}")

    if raw:
        typer.echo(audit.agent_prompt)
    else:
        print_prompt_panel(audit.agent_prompt, copied=copied)


@app.command(name="init")
def init_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner (kept for CLI consistency)"),
    ] = False,
) -> None:
    """
    🛠️ Initialize starter test scaffolding and tailored test suites for discovered modules.
    """
    _require("cli.init")
    audit = _analyze_project(project_dir=path, execute_tests=False)
    created = initialize_test_scaffold(audit.project, path)

    if created:
        console.print("[bold green]✨ Initialized test scaffolding & stubs:[/bold green]")
        for c in created:
            console.print(f"  [cyan]+ {c}[/cyan]")
    else:
        console.print("[bold yellow]Test infrastructure already exists or no new files needed.[/bold yellow]")


@app.command(name="integrate")
@app.command(name="setup")
def integrate_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    cursor: Annotated[
        bool,
        typer.Option(
            "--cursor/--no-cursor", help="Generate Cursor AI rule files (.cursorrules, .cursor/rules/)"
        ),
    ] = True,
    claude: Annotated[
        bool,
        typer.Option("--claude/--no-claude", help="Generate Claude Code instructions (CLAUDE.md)"),
    ] = True,
    copilot: Annotated[
        bool,
        typer.Option(
            "--copilot/--no-copilot",
            help="Generate GitHub Copilot instructions (.github/copilot-instructions.md)",
        ),
    ] = True,
    agents: Annotated[
        bool,
        typer.Option("--agents/--no-agents", help="Generate Universal Agent guide (AGENTS.md)"),
    ] = True,
    config: Annotated[
        bool,
        typer.Option("--config/--no-config", help="Generate TimmyTest configuration (.timmytest.yml)"),
    ] = True,
    ci: Annotated[
        bool,
        typer.Option(
            "--ci/--no-ci", help="Generate GitHub Actions CI workflow (.github/workflows/timmytest.yml)"
        ),
    ] = False,
    mcp: Annotated[
        bool,
        typer.Option("--mcp/--no-mcp", help="Generate MCP configuration snippet (.cursor/mcp.json)"),
    ] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Re-integrate even if TimmyTest rules are already present (appends; never overwrites existing content)",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview file changes without writing to disk"),
    ] = False,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    🚀 Integrate TimmyTest into any project: auto-generate AI agent rules, configs, and MCP tools.
    """
    _require("cli.integrate")
    if not no_banner:
        print_banner()

    result = integrate_project(
        project_dir=path,
        include_cursor=cursor,
        include_claude=claude,
        include_copilot=copilot,
        include_agents=agents,
        include_config=config,
        include_ci=ci,
        include_mcp=mcp,
        force=force,
        dry_run=dry_run,
    )

    root = path.resolve()
    prefix = "[bold yellow][DRY RUN][/bold yellow] " if dry_run else ""

    console.print(
        f"\n{prefix}[bold green]⚡ TimmyTest Integration Summary[/bold green] "
        f"({result.ecosystem.value.title()} / {result.framework.value}):\n"
    )

    if result.created_files:
        console.print("[bold green]Created Files:[/bold green]")
        for f in result.created_files:
            rel = f.relative_to(root) if f.is_relative_to(root) else f
            console.print(f"  [green]+ {rel}[/green]")

    if result.modified_files:
        console.print("[bold cyan]Updated / Appended Files:[/bold cyan]")
        for f in result.modified_files:
            rel = f.relative_to(root) if f.is_relative_to(root) else f
            console.print(f"  [cyan]~ {rel}[/cyan]")

    if result.skipped_files:
        console.print("[bold dim]Already Configured / Skipped:[/bold dim]")
        for f in result.skipped_files:
            rel = f.relative_to(root) if f.is_relative_to(root) else f
            console.print(f"  [dim]• {rel}[/dim]")

    console.print(
        "\n[bold cyan]🤖 AI agents in this repo are now pre-configured to test with zero token waste![/bold cyan]"
    )
    console.print("[dim]Try running: 'timmytest check' or 'timmytest mcp'[/dim]\n")


@app.command(name="agent")
def agent_command(
    path: Annotated[
        Path,
        typer.Argument(help="Target project directory path", exists=True, file_okay=False, dir_okay=True),
    ] = Path("."),
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Test execution timeout in seconds"),
    ] = 60,
    filter_pattern: Annotated[
        str | None,
        typer.Option("--filter", "-k", help="Filter tests by name pattern"),
    ] = None,
    cmd: Annotated[
        str | None,
        typer.Option("--cmd", help="Custom test command to execute"),
    ] = None,
    no_run: Annotated[
        bool,
        typer.Option("--no-run", help="Skip test execution (static scan only)"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output in machine JSON format"),
    ] = False,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner (kept for CLI consistency)"),
    ] = False,
) -> None:
    """
    🤖 Direct zero-noise output optimized for AI coding agents (Claude, Cursor, Antigravity).
    """
    _require("cli.agent")
    audit = _analyze_project(
        project_dir=path,
        custom_cmd=cmd,
        execute_tests=not no_run,
        timeout_seconds=timeout,
        filter_pattern=filter_pattern,
    )
    if json_output:
        typer.echo(export_audit_to_json(audit))
    else:
        typer.echo(audit.agent_prompt)


@app.command(name="ui")
@app.command(name="app")
def ui_command(
    path: Annotated[
        Path | None,
        typer.Argument(help="Optional project directory to pre-select when creating a workspace"),
    ] = None,
    fresh: Annotated[
        bool,
        typer.Option("--fresh", help="Replay the full onboarding (setup, language, workspace)"),
    ] = False,
) -> None:
    """
    🎮 Launch the full-screen TimmyTest application (splash, setup, workspaces, dashboard).
    """
    _require("cli.ui")
    from timmytest.tui.app import launch

    launch(fresh=fresh, start_path=path.resolve() if path else None)


@app.command(name="mcp")
def mcp_command() -> None:
    """
    ⚡ Start the Model Context Protocol (MCP) server for native tool integration with AI agents.
    """
    _require("cli.mcp")
    run_mcp_server()


@app.command(name="version")
def version_command(
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner (kept for CLI consistency)"),
    ] = False,
) -> None:
    """
    Show TimmyTest version.
    """
    typer.echo(f"timmytest version {__version__}")


if __name__ == "__main__":
    app()
