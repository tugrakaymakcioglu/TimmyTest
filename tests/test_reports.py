"""Tests for reporting modules (Console, JSON export, Markdown)."""

import json
from pathlib import Path

from timmytest.detector.models import (
    Ecosystem,
    FailureDetail,
    Priority,
    ProjectAudit,
    ProjectInfo,
    SourceModule,
    TestFramework,
    TestGap,
    TestModule,
    TestRunResult,
)
from timmytest.reports.console import (
    print_failures,
    print_project_summary,
    print_prompt_panel,
    print_test_gaps,
    print_test_run_summary,
)
from timmytest.reports.json_export import export_audit_to_json
from timmytest.reports.markdown import generate_markdown_report


def _make_dummy_audit(tmp_path: Path) -> ProjectAudit:
    proj = ProjectInfo(
        root_dir=str(tmp_path),
        project_name="DemoReport",
        ecosystem=Ecosystem.PYTHON,
        test_framework=TestFramework.PYTEST,
        test_command="pytest -ra",
        source_modules=[
            SourceModule(
                rel_path="src/main.py",
                abs_path=str(tmp_path / "src/main.py"),
                language="py",
                line_count=30,
            )
        ],
        test_modules=[
            TestModule(
                rel_path="tests/test_main.py",
                abs_path=str(tmp_path / "tests/test_main.py"),
                framework=TestFramework.PYTEST,
                test_functions=["test_main"],
            )
        ],
        test_gaps=[
            TestGap(
                source_module="src/untested.py",
                suggested_test_file="tests/test_untested.py",
                priority=Priority.HIGH,
                reason="Untested service file",
            )
        ],
        readiness_score=50.0,
    )

    tr = TestRunResult(
        ecosystem=Ecosystem.PYTHON,
        framework=TestFramework.PYTEST,
        command="pytest -ra",
        total=2,
        passed=1,
        failed=1,
        failures=[
            FailureDetail(
                test_name="tests/test_main.py::test_main",
                file_path="tests/test_main.py",
                line_number=10,
                error_type="AssertionError",
                message="assert 1 == 2",
                suggested_fix="Fix value mismatch",
            )
        ],
        has_executed=True,
    )

    return ProjectAudit(
        project=proj,
        test_run=tr,
        agent_prompt="Mock prompt",
    )


def test_console_renderers(temp_project_dir: Path):
    audit = _make_dummy_audit(temp_project_dir)
    print_project_summary(audit.project)
    print_test_run_summary(audit.test_run)
    print_failures(audit.test_run)
    print_test_gaps(audit.project)
    print_prompt_panel(audit.agent_prompt, copied=True)


def test_json_and_markdown_export(temp_project_dir: Path):
    audit = _make_dummy_audit(temp_project_dir)
    json_path = temp_project_dir / "audit.json"
    md_path = temp_project_dir / "audit.md"

    json_str = export_audit_to_json(audit, output_path=json_path)
    assert json_path.exists()
    data = json.loads(json_str)
    assert data["project"]["project_name"] == "DemoReport"

    md_str = generate_markdown_report(audit, output_path=md_path)
    assert md_path.exists()
    assert "# TimmyTest Audit Report: DemoReport" in md_str
    assert "AssertionError" in md_str
