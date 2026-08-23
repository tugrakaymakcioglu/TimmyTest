"""Tests for git-aware incremental test selection."""

import subprocess
from pathlib import Path

import pytest

from timmytest.detector.models import SourceModule, TestModule
from timmytest.git_changed import (
    NotAGitRepositoryError,
    get_changed_files,
    select_affected_tests,
)


def _src(rel, **kw):
    return SourceModule(rel_path=rel, abs_path=rel, language="python", **kw)


def _test(rel, imports=None):
    return TestModule(rel_path=rel, abs_path=rel, imported_modules=imports or [])


def test_select_affected_tests_direct_test_file():
    changed = ["tests/test_auth.py"]
    sources = [_src("src/auth.py")]
    tests = [_test("tests/test_auth.py")]
    affected = select_affected_tests(changed, sources, tests)
    assert affected == ["tests/test_auth.py"]


def test_select_affected_tests_maps_source_to_test():
    changed = ["src/auth.py"]
    sources = [_src("src/auth.py")]
    tests = [_test("tests/test_auth.py", imports=["auth"])]
    affected = select_affected_tests(changed, sources, tests)
    assert affected == ["tests/test_auth.py"]


def test_select_affected_tests_ignores_unrelated():
    changed = ["src/unrelated.py"]
    sources = [_src("src/auth.py"), _src("src/unrelated.py")]
    tests = [_test("tests/test_auth.py")]
    affected = select_affected_tests(changed, sources, tests)
    assert affected == []


def test_select_affected_tests_dedupes():
    changed = ["src/auth.py", "tests/test_auth.py"]
    sources = [_src("src/auth.py")]
    tests = [_test("tests/test_auth.py", imports=["auth"])]
    affected = select_affected_tests(changed, sources, tests)
    assert affected == ["tests/test_auth.py"]


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.co"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True)


def test_get_changed_files_detects_working_tree_changes(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v2", encoding="utf-8")
    (tmp_path / "b.txt").write_text("new", encoding="utf-8")
    changed = get_changed_files(tmp_path)
    assert "a.txt" in changed
    assert "b.txt" in changed


def test_get_changed_files_since_ref(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v2", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "second"], check=True)
    # Since HEAD~1, a.txt should appear.
    changed = get_changed_files(tmp_path, ref="HEAD~1")
    assert "a.txt" in changed


def test_get_changed_files_are_relative_to_the_audited_directory(tmp_path):
    """A project nested below its .git must get paths it can actually match."""
    _init_git_repo(tmp_path)
    package = tmp_path / "packages" / "api"
    package.mkdir(parents=True)
    (package / "service.py").write_text("def call():\n    return 1\n", encoding="utf-8")

    changed = get_changed_files(package)

    # Relative to the package, not to the repository root.
    assert "service.py" in changed
    assert "packages/api/service.py" not in changed


def test_get_changed_files_raises_outside_repo(tmp_path):
    with pytest.raises(NotAGitRepositoryError):
        get_changed_files(tmp_path)
