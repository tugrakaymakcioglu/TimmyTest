"""Regression cases for false-green audits and mixed-language repositories."""

from pathlib import Path

from timmytest import analysis
from timmytest.detector.models import (
    CoverageReport,
    Ecosystem,
    FileCoverage,
    SourceModule,
    TestFramework,
    TestModule,
    TestRunResult,
)
from timmytest.git_changed import select_affected_tests
from timmytest.registry.loader import detect_from_registry, detect_workspaces
from timmytest.runner.generic_runner import GenericRunner
from timmytest.scaffolder.init_tests import initialize_test_scaffold


def test_scaffold_does_not_claim_coverage(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text("def charge(): raise RuntimeError()\n")
    before = analysis.analyze_project(tmp_path, execute_tests=False)
    initialize_test_scaffold(before.project, tmp_path)
    after = analysis.analyze_project(tmp_path, execute_tests=False)
    assert after.project.readiness_score == 0
    assert len(after.project.test_gaps) == 1
    assert "pytest.skip" in (tmp_path / "test_billing.py").read_text()


def test_comment_only_python_test_is_not_evidence(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "pay.py").write_text("def pay(): return True\n")
    (tmp_path / "tests" / "test_pay.py").write_text("# TODO: write tests\n")
    audit = analysis.analyze_project(tmp_path, execute_tests=False)
    assert audit.project.readiness_score == 0


def test_old_assert_true_stub_is_not_evidence(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "pay.py").write_text("def pay(): return True\n")
    (tmp_path / "tests" / "test_pay.py").write_text(
        'def test_pay():\n    """old scaffold"""\n    assert True\n'
    )
    audit = analysis.analyze_project(tmp_path, execute_tests=False)
    assert audit.project.readiness_score == 0


def test_failed_gradle_build_with_passed_case_stays_failed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "timmytest.runner.generic_runner.execute_safe_subprocess",
        lambda *a, **k: (1, "com.x.FooTest > works PASSED\nBUILD FAILED", False),
    )
    result = GenericRunner().run_tests(
        tmp_path, "gradle test", ecosystem=Ecosystem.KOTLIN, framework=TestFramework.GRADLE,
    )
    assert result.passed == 1
    assert result.exit_code == 1
    assert result.failed + result.errors >= 1


def test_cli_failure_gate_respects_nonzero_process_exit():
    from timmytest.cli import _failing_count
    from timmytest.detector.models import ProjectAudit, ProjectInfo

    audit = ProjectAudit(
        project=ProjectInfo(root_dir=".", project_name="sample", ecosystem=Ecosystem.KOTLIN, test_framework=TestFramework.GRADLE),
        test_run=TestRunResult(ecosystem=Ecosystem.KOTLIN, framework=TestFramework.GRADLE,
                               passed=1, total=1, exit_code=1, has_executed=True),
    )
    assert _failing_count(audit) > 0


def test_plain_dart_web_folder_is_not_flutter(tmp_path: Path):
    (tmp_path / "pubspec.yaml").write_text("name: sample\ndependencies:\n  test: ^1.0.0\n")
    (tmp_path / "web").mkdir()
    assert detect_from_registry(tmp_path)[:3] == ("dart", "dart_test", "dart test")


def test_detect_workspaces_in_polyglot_and_nested_repo(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="example"\n')
    (tmp_path / "package.json").write_text('{"scripts":{"test":"node --test"}}')
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "Cargo.toml").write_text('[package]\nname="child"\nversion="0.1.0"\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "requirements.txt").write_text("pytest\n")
    targets = detect_workspaces(tmp_path)
    assert {(path.relative_to(tmp_path).as_posix(), eco) for path, eco, _, _ in targets} == {
        (".", "python"), (".", "node"), ("child", "rust"),
    }


def test_go_scaffold_is_skipped_and_not_coverage(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module example.com/sample\n\ngo 1.21\n")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n")
    before = analysis.analyze_project(tmp_path, execute_tests=False)
    initialize_test_scaffold(before.project, tmp_path)
    after = analysis.analyze_project(tmp_path, execute_tests=False)
    assert after.project.readiness_score == 0
    assert 't.Skip(' in (tmp_path / "main_test.go").read_text()


def test_analysis_runs_every_configured_ecosystem(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="example"\n')
    (tmp_path / "package.json").write_text('{"scripts":{"test":"node --test"}}')
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return TestRunResult(
            ecosystem=kwargs["ecosystem"], framework=kwargs["framework"],
            command=kwargs["custom_cmd"], total=1, passed=1, has_executed=True,
        )

    monkeypatch.setattr(analysis, "run_project_tests", fake_run)
    audit = analysis.analyze_project(tmp_path, execute_tests=True)
    assert {call["ecosystem"] for call in calls} == {Ecosystem.PYTHON, Ecosystem.NODE}
    assert len(audit.test_runs) == 2
    assert audit.test_run.passed == 2


def test_nested_only_project_still_runs(monkeypatch, tmp_path: Path):
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "Cargo.toml").write_text('[package]\nname="child"\nversion="0.1.0"\n')
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return TestRunResult(ecosystem=kwargs["ecosystem"], framework=kwargs["framework"],
                             command=kwargs["custom_cmd"], has_executed=True)

    monkeypatch.setattr(analysis, "run_project_tests", fake_run)
    audit = analysis.analyze_project(tmp_path, execute_tests=True)
    assert len(calls) == 1
    assert calls[0]["ecosystem"] == Ecosystem.RUST
    assert audit.test_run.has_executed


def test_changed_source_selects_all_related_tests():
    source = SourceModule(rel_path="src/auth.py", abs_path="", language="py")
    tests = [
        TestModule(rel_path=f"tests/test_auth_{n}.py", abs_path="", test_functions=["test_login"], imported_modules=["auth"])
        for n in ("unit", "integration")
    ]
    assert select_affected_tests(["src/auth.py"], [source], tests) == [
        "tests/test_auth_integration.py", "tests/test_auth_unit.py",
    ]
    assert select_affected_tests(["pyproject.toml"], [source], tests) == [
        "tests/test_auth_integration.py", "tests/test_auth_unit.py",
    ]


def test_unmapped_change_falls_back_to_full_suite(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="sample"\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def app(): return 1\n")
    monkeypatch.setattr("timmytest.git_changed.get_changed_files", lambda *a, **k: ["src/app.py"])
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return TestRunResult(ecosystem=kwargs["ecosystem"], framework=kwargs["framework"],
                             command=kwargs["custom_cmd"], has_executed=True)

    monkeypatch.setattr(analysis, "run_project_tests", fake_run)
    analysis.analyze_project(tmp_path, execute_tests=True, changed=True)
    assert len(calls) == 1
    assert calls[0]["test_paths"] is None


def test_coverage_gap_keeps_same_stem_in_other_directory():
    from timmytest.detector.models import Priority, TestGap

    existing = TestGap(
        source_module="auth/utils.py", suggested_test_file="", priority=Priority.MEDIUM, reason="missing",
    )
    report = CoverageReport(source="coverage.json", total_percent=50, files=[
        FileCoverage(path="billing/utils.py", percent=20),
    ])
    result = analysis._enrich_gaps_with_coverage([existing], report, 60)
    assert {gap.source_module for gap in result} == {"auth/utils.py", "billing/utils.py"}
