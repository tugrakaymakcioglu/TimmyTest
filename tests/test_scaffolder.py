"""Tests for test scaffold generation."""

from pathlib import Path

from timmytest.detector.models import Ecosystem, ProjectInfo, TestFramework
from timmytest.scaffolder.init_tests import initialize_test_scaffold


def test_scaffold_python(temp_project_dir: Path):
    proj = ProjectInfo(
        root_dir=str(temp_project_dir),
        project_name="PyDemo",
        ecosystem=Ecosystem.PYTHON,
        test_framework=TestFramework.PYTEST,
    )
    created = initialize_test_scaffold(proj, temp_project_dir)
    assert "tests/conftest.py" in created
    assert "tests/test_example.py" in created
    assert (temp_project_dir / "tests" / "conftest.py").exists()


def test_scaffold_node(temp_project_dir: Path):
    proj = ProjectInfo(
        root_dir=str(temp_project_dir),
        project_name="NodeDemo",
        ecosystem=Ecosystem.NODE,
        test_framework=TestFramework.VITEST,
    )
    created = initialize_test_scaffold(proj, temp_project_dir)
    assert any("example.test" in c for c in created)


def test_scaffold_rust(temp_project_dir: Path):
    proj = ProjectInfo(
        root_dir=str(temp_project_dir),
        project_name="RustDemo",
        ecosystem=Ecosystem.RUST,
        test_framework=TestFramework.CARGO,
    )
    created = initialize_test_scaffold(proj, temp_project_dir)
    assert "tests/integration_test.rs" in created


def test_scaffold_go(temp_project_dir: Path):
    proj = ProjectInfo(
        root_dir=str(temp_project_dir),
        project_name="GoDemo",
        ecosystem=Ecosystem.GO,
        test_framework=TestFramework.GO_TEST,
    )
    created = initialize_test_scaffold(proj, temp_project_dir)
    assert "main_test.go" in created
