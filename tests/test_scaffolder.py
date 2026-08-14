"""Tests for test scaffold generation."""

from pathlib import Path

from timmytest.detector.models import (
    Ecosystem,
    FunctionDetail,
    Priority,
    ProjectInfo,
    TestFramework,
    TestGap,
)
from timmytest.scaffolder.init_tests import initialize_test_scaffold


def test_scaffold_python_default(temp_project_dir: Path):
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


def test_scaffold_python_with_gaps(temp_project_dir: Path):
    proj = ProjectInfo(
        root_dir=str(temp_project_dir),
        project_name="PyDemo",
        ecosystem=Ecosystem.PYTHON,
        test_framework=TestFramework.PYTEST,
        test_gaps=[
            TestGap(
                source_module="src/auth.py",
                suggested_test_file="tests/test_auth.py",
                priority=Priority.HIGH,
                reason="High priority auth",
                function_details=[
                    FunctionDetail(
                        name="login",
                        signature="(user: str, pass: str) -> bool",
                        docstring="Verify user",
                    )
                ],
                classes_to_test=["AuthManager"],
            )
        ],
    )
    created = initialize_test_scaffold(proj, temp_project_dir)
    assert "tests/test_auth.py" in created
    auth_test_content = (temp_project_dir / "tests" / "test_auth.py").read_text(encoding="utf-8")
    assert "def test_login():" in auth_test_content
    assert "def test_auth_authmanager_initialization():" in auth_test_content


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
