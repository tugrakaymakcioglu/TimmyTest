"""TimmyTest CLI entrypoint."""

import contextlib
import sys
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


def _analyze_project(
    project_dir: Path,
    custom_cmd: str | None = None,
    execute_tests: bool = True,
    timeout_seconds: int = 60,
    filter_pattern: str | None = None,
) -> ProjectAudit:
    """Core analysis orchestrator."""
    root = project_dir.resolve()
    project_name = root.name

    # 1. Detect ecosystem & framework
    ecosystem, framework, default_cmd, configs = detect_ecosystem(root)
    test_cmd = custom_cmd or default_cmd

    # 2. Scan source and test files
    source_modules, test_modules = scan_project_structure(root, ecosystem, framework)

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
        test_run = run_project_tests(
            root_dir=root,
            ecosystem=ecosystem,
            framework=framework,
            custom_cmd=custom_cmd,
            timeout_seconds=timeout_seconds,
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
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Run complete audit: Scan modules, detect test gaps, run tests, diagnose failures, and generate AI prompt.
    """
    audit = _analyze_project(
        project_dir=path,
        custom_cmd=cmd,
        execute_tests=not no_run,
        timeout_seconds=timeout,
        filter_pattern=filter_pattern,
    )

    if json_output:
        typer.echo(export_audit_to_json(audit))
        return

    if not no_banner:
        print_banner()

    print_project_summary(audit.project)
    if audit.test_run.has_executed:
        print_test_run_summary(audit.test_run)
        print_failures(audit.test_run)
    print_test_gaps(audit.project)

    copied = False
    if copy_prompt_flag:
        copied = copy_to_clipboard(audit.agent_prompt)

    print_prompt_panel(audit.agent_prompt, copied=copied)

    if save_prompt:
        save_prompt.write_text(audit.agent_prompt, encoding="utf-8")
        console.print(f"[bold green]✓ AI Agent Prompt saved to:[/bold green] {save_prompt}")

    if save_report:
        save_report.write_text(audit.summary_markdown, encoding="utf-8")
        console.print(f"[bold green]✓ Audit Report saved to:[/bold green] {save_report}")


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
    no_banner: Annotated[
        bool,
        typer.Option("--no-banner", help="Omit ASCII banner"),
    ] = False,
) -> None:
    """
    ⚡ Execute tests, parse PASS/FAIL results, and display rich failure diagnostics & fix suggestions.
    """
    audit = _analyze_project(
        project_dir=path,
        custom_cmd=cmd,
        execute_tests=True,
        timeout_seconds=timeout,
        filter_pattern=filter_pattern,
    )

    if json_output:
        typer.echo(export_audit_to_json(audit))
        return

    if not no_banner:
        print_banner()

    if not only_failures:
        print_project_summary(audit.project)
        print_test_run_summary(audit.test_run)

    print_failures(audit.test_run)


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
    🛠️ Initialize starter test scaffolding (tests/ directory and config) for the project.
    """
    audit = _analyze_project(project_dir=path, execute_tests=False)
    created = initialize_test_scaffold(audit.project, path)

    if created:
        console.print("[bold green]✨ Initialized test scaffolding:[/bold green]")
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
