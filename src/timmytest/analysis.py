"""Shared audit orchestration used by both the CLI and the terminal application."""

from pathlib import Path

from timmytest.config import TimmyConfig, load_project_config
from timmytest.coverage import find_low_coverage_files, parse_coverage_report
from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import (
    CoverageReport,
    Priority,
    ProjectAudit,
    ProjectInfo,
    TestGap,
    TestRunResult,
)
from timmytest.detector.scanner import scan_project_structure
from timmytest.diagnostics.analyzer import enrich_test_failures
from timmytest.prompt.generator import generate_agent_prompt
from timmytest.reports.markdown import generate_markdown_report
from timmytest.runner.orchestrator import run_project_tests


def _enrich_gaps_with_coverage(
    gaps: list[TestGap],
    coverage: CoverageReport,
    threshold: float,
) -> list[TestGap]:
    """Append low-coverage files as additional gaps, without duplicating untested files."""
    already_flagged = {g.source_module.replace("\\", "/") for g in gaps}
    enriched = list(gaps)

    for fc in find_low_coverage_files(coverage, threshold):
        norm = fc.path.replace("\\", "/")
        stem = Path(norm).stem
        # Skip files already flagged as fully untested.
        if norm in already_flagged:
            continue
        if any(stem == Path(src).stem for src in already_flagged):
            continue
        enriched.append(
            TestGap(
                source_module=norm,
                suggested_test_file="",
                priority=Priority.MEDIUM,
                reason=f"Low test coverage ({fc.percent}% < {threshold}%) — tests exist but leave lines unexecuted",
                functions_to_test=[],
                classes_to_test=[],
            )
        )
    return enriched


def analyze_project(
    project_dir: Path,
    custom_cmd: str | None = None,
    execute_tests: bool = True,
    timeout_seconds: int = 60,
    filter_pattern: str | None = None,
    config: TimmyConfig | None = None,
    test_paths: list[str] | None = None,
    coverage: bool = False,
    coverage_path: Path | None = None,
    coverage_threshold: float = 60.0,
    changed: bool = False,
    since: str | None = None,
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

    # 3a. Incremental selection: restrict the run to tests affected by git changes.
    effective_test_paths = test_paths
    if (changed or since) and effective_test_paths is None:
        from timmytest.git_changed import get_affected_test_paths

        affected = get_affected_test_paths(root, source_modules, test_modules, ref=since)
        # Empty selection is meaningful, not a signal to fall back to the whole
        # suite: `--changed` promises "run what my diff touched", so a clean
        # tree must skip execution entirely - the previous fallback re-ran
        # everything, the exact cost the flag exists to avoid.
        if not affected:
            execute_tests = False
            effective_test_paths = []
        else:
            effective_test_paths = affected

    # 3b. Coverage-aware analysis (optional): parse a coverage report and enrich gaps.
    coverage_report = (
        parse_coverage_report(root, coverage_path) if (coverage or coverage_path is not None) else None
    )
    if coverage_report is not None:
        gaps = _enrich_gaps_with_coverage(gaps, coverage_report, coverage_threshold)

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
        coverage=coverage_report,
    )

    # 4. Execute tests if requested
    if execute_tests and test_modules:
        # `timeout_seconds` is already resolved by the caller when it can be; the
        # config value is the fallback for callers that pass 0/None.
        effective_timeout = timeout_seconds or cfg.timeout_seconds
        test_run = run_project_tests(
            root_dir=root,
            ecosystem=ecosystem,
            framework=framework,
            custom_cmd=test_cmd,
            timeout_seconds=effective_timeout,
            filter_pattern=filter_pattern,
            test_paths=effective_test_paths,
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
