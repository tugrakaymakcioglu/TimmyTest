"""Tests for gap analyzer and readiness scoring."""

from pathlib import Path

from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import Ecosystem, Priority, SourceModule, TestFramework, TestModule


def test_gap_analyzer_detects_missing_module(temp_project_dir: Path):
    source_modules = [
        SourceModule(
            rel_path="src/auth.py",
            abs_path=str(temp_project_dir / "src/auth.py"),
            language="py",
            line_count=45,
            functions=["login", "logout"],
            classes=["AuthService"],
            is_entrypoint=False,
            is_utility=False,
            is_model=False,
            is_route=False,
        ),
        SourceModule(
            rel_path="src/api/routes.py",
            abs_path=str(temp_project_dir / "src/api/routes.py"),
            language="py",
            line_count=120,
            functions=["handle_request"],
            classes=[],
            is_entrypoint=False,
            is_utility=False,
            is_model=False,
            is_route=True,
        ),
    ]

    test_modules = [
        TestModule(
            rel_path="tests/test_auth.py",
            abs_path=str(temp_project_dir / "tests/test_auth.py"),
            framework=TestFramework.PYTEST,
            test_functions=["test_login"],
            line_count=20,
        )
    ]

    gaps, score = analyze_test_gaps(source_modules, test_modules, Ecosystem.PYTHON, temp_project_dir)

    assert len(gaps) == 1
    assert gaps[0].source_module == "src/api/routes.py"
    assert gaps[0].priority == Priority.HIGH
    assert "routes" in gaps[0].suggested_test_file
    assert score < 100.0


def test_gap_analyzer_100_percent_when_all_covered(temp_project_dir: Path):
    source_modules = [
        SourceModule(
            rel_path="src/utils.py",
            abs_path=str(temp_project_dir / "src/utils.py"),
            language="py",
            line_count=25,
            functions=["format_date"],
            classes=[],
        )
    ]

    test_modules = [
        TestModule(
            rel_path="tests/test_utils.py",
            abs_path=str(temp_project_dir / "tests/test_utils.py"),
            framework=TestFramework.PYTEST,
            test_functions=["test_format_date"],
            line_count=15,
        )
    ]

    gaps, score = analyze_test_gaps(source_modules, test_modules, Ecosystem.PYTHON, temp_project_dir)

    assert len(gaps) == 0
    assert score == 100.0
