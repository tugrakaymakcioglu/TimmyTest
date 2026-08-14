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

from timmytest import __version__
from timmytest.banner import print_banner
from timmytest.config import TimmyConfig, load_project_config
from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import (
    ProjectAudit,
    ProjectInfo,
    TestRunResult,
)
from timmytest.detector.scanner import scan_project_structure
from timmytest.diagnostics.analyzer import enrich_test_failures
from timmytest.prompt.clipboard import copy_to_clipboard
from timmytest.prompt.generator import generate_agent_prompt
from timmytest.reports.console import (
    console,
    print_failures,
    print_project_summary,
    print_prompt_panel,
    print_test_gaps,
    print_test_run_summary,
)
from timmytest.reports.json_export import export_audit_to_json
from timmytest.reports.markdown import generate_markdown_report
from timmytest.runner.orchestrator import run_project_tests
from timmytest.scaffolder.init_tests import initialize_test_scaffold

app = typer.Typer(
    name="timmytest",
    help="⚡ Zero-token terminal test runner, test-gap analyzer, and AI agent prompt generator.",
    add_completion=False,
    rich_markup_mode="rich",
)


def _get_project_mtimes(root: Path, config: TimmyConfig) -> dict[str, float]:
    """Get modification timestamps of all tracked project files."""
    mtimes: dict[str, float] = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel_parts = set(p.relative_to(root).parts)
            if any(ign in rel_parts for ign in config.ignored_dirs):
                continue
            with contextlib.suppress(Exception):
                mtimes[str(p)] = p.stat().st_mtime
    return mtimes


def _analyze_project(
    project_dir: Path,
    custom_cmd: str | None = None,
    execute_tests: bool = True,
    timeout_seconds: int = 60,
    filter_pattern: str | None = None,
    config: TimmyConfig | None = None,
) -> ProjectAudit:
    """Core analysis orchestrator."""
    root = project_dir.resolve()
    project_name = root.name
    cfg = config or load_project_config(root)

    # 1. Detect ecosystem & framework
    ecosystem, framework, default_cmd, configs = detect_ecosystem(root)
    test_cmd = custom_cmd or cfg.custom_test_cmd or default_cmd

    # 2. Scan source and test files
    source_modules, test_modules = scan_project_structure(
        root,
        ecosystem,
        framework,
        custom_ignored_dirs=cfg.ignored_dirs,
        custom_ignored_files=cfg.ignored_files,
    )

    # 3. Analyze test gaps
    gaps, readiness_score = analyze_test_gaps(source_modules, test_modules, ecosystem, root)

    project_info = ProjectInfo(
        root_dir=str(root),
        project_name=project_name,
        ecosystem=ecosystem,
        test_framework=framework,
        config_files=configs,
        test_command=test_cmd,
        source_modules=source_modules,
        test_modules=test_modules,
        test_gaps=gaps,
        total_source_files=len(source_modules),
        total_test_files=len(test_modules),
        readiness_score=readiness_score,
    )

    # 4. Execute tests if requested
    if execute_tests and test_modules:
        effective_timeout = timeout_seconds or cfg.timeout_seconds
        test_run = run_project_tests(
            root_dir=root,
            ecosystem=ecosystem,
            framework=framework,
            custom_cmd=test_cmd,
            timeout_seconds=effective_timeout,
            filter_pattern=filter_pattern,
        )
        test_run = enrich_test_failures(test_run)
    else:
        test_run = TestRunResult(
            ecosystem=ecosystem,
            framework=framework,
            command=test_cmd,
            total=0,
            has_executed=False,
        )

    # 5. Generate AI agent prompt
    agent_prompt = generate_agent_prompt(project_info, test_run)

    # 6. Form unified audit
    audit = ProjectAudit(
        project=project_info,
        test_run=test_run,
        agent_prompt=agent_prompt,
    )
    audit.summary_markdown = generate_markdown_report(audit)
    return audit


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
        typer.Option("--no-run", help="Skip running tests (static gap analysis only)"),
    ] = False,
    safe_dry_run: Annotated[
        bool,
        typer.Option("--safe", "--dry-run", help="Safe mode: analyze without running tests on untrusted code"),
    ] = False,
    fail_under: Annotated[
        float | None,
        typer.Option("--fail-under", help="Minimum required test readiness score percentage (0-100)"),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch for file changes and continuously re-audit"),
    ] = False,
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Run complete audit: Scan modules, detect test gaps, run tests, diagnose failures, and generate AI prompt.
    """
    config = load_project_config(path)
    should_run = not (no_run or safe_dry_run)

    def _execute_single_audit() -> ProjectAudit:
        audit = _analyze_project(
            project_dir=path,
            custom_cmd=cmd,
            execute_tests=should_run,
            timeout_seconds=timeout,
            filter_pattern=filter_pattern,
            config=config,
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

        copied = False
        if copy_prompt_flag and config.copy_prompt:
            copied = copy_to_clipboard(audit.agent_prompt)

        print_prompt_panel(audit.agent_prompt, copied=copied)

        if save_prompt:
            save_prompt.write_text(audit.agent_prompt, encoding="utf-8")
            console.print(f"[bold green]✓ AI Agent Prompt saved to:[/bold green] {save_prompt}")

        if save_report:
            save_report.write_text(audit.summary_markdown, encoding="utf-8")
            console.print(f"[bold green]✓ Audit Report saved to:[/bold green] {save_report}")

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
                    console.print("\n[bold yellow]🔄 File change detected. Re-running audit...[/bold yellow]\n")
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

    if audit.test_run.has_executed and audit.test_run.failed > 0 and config.fail_on_test_failure:
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
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    🔍 Fast static scan: Discover source modules, existing test files, and missing test gaps.
    """
    audit = _analyze_project(project_dir=path, execute_tests=False)

    if json_output:
        typer.echo(export_audit_to_json(audit))
        return

    if not no_banner:
        print_banner()

    print_project_summary(audit.project)
    print_test_gaps(audit.project)


@app.command(name="run")
def run_command(
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
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Execute tests, parse PASS/FAIL results, and display rich failure diagnostics & fix suggestions.
    """
    config = load_project_config(path)

    def _execute_run() -> ProjectAudit:
        audit = _analyze_project(
            project_dir=path,
            custom_cmd=cmd,
            execute_tests=True,
            timeout_seconds=timeout,
            filter_pattern=filter_pattern,
            config=config,
        )

        if json_output:
            typer.echo(export_audit_to_json(audit))
            return audit

        if not no_banner:
            print_banner()

        if not only_failures:
            print_project_summary(audit.project)
            print_test_run_summary(audit.test_run)

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
                    console.print("\n[bold yellow]🔄 File change detected. Re-running tests...[/bold yellow]\n")
                    _execute_run()
                    last_mtimes = current_mtimes
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping watch mode.[/bold yellow]")
            return

    if audit.test_run.has_executed and audit.test_run.failed > 0 and config.fail_on_test_failure:
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
) -> None:
    """
    🤖 Generate an ultra-dense, token-optimized prompt for AI coding agents.
    """
    audit = _analyze_project(project_dir=path, execute_tests=not no_run)

    copied = False
    if copy_flag:
        copied = copy_to_clipboard(audit.agent_prompt)

    if output_file:
        output_file.write_text(audit.agent_prompt, encoding="utf-8")
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
) -> None:
    """
    🛠️ Initialize starter test scaffolding and tailored test suites for discovered modules.
    """
    audit = _analyze_project(project_dir=path, execute_tests=False)
    created = initialize_test_scaffold(audit.project, path)

    if created:
        console.print("[bold green]✨ Initialized test scaffolding & stubs:[/bold green]")
        for c in created:
            console.print(f"  [cyan]+ {c}[/cyan]")
    else:
        console.print("[bold yellow]Test infrastructure already exists or no new files needed.[/bold yellow]")


@app.command(name="version")
def version_command() -> None:
    """
    Show TimmyTest version.
    """
    typer.echo(f"timmytest version {__version__}")


if __name__ == "__main__":
    app()
