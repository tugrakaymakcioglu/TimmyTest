"""Tests for the shared pruning filesystem walk."""

from pathlib import Path

from timmytest.walk import IGNORED_DIRS, has_file_with_extension, iter_files, walk_dirs


def _build_tree(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    deep = root / "node_modules" / "left-pad" / "lib"
    deep.mkdir(parents=True)
    (deep / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")


def test_iter_files_skips_dependency_and_vcs_directories(tmp_path: Path):
    _build_tree(tmp_path)
    found = {p.name for p in iter_files(tmp_path)}
    assert found == {"app.py"}


def test_walk_never_enters_pruned_directories(tmp_path: Path):
    """Pruning must happen before descent, not as a post-filter."""
    _build_tree(tmp_path)
    visited = [dirpath for dirpath, _files in walk_dirs(tmp_path)]
    assert not any("node_modules" in d for d in visited)
    assert not any(".git" in d for d in visited)


def test_has_file_with_extension_finds_and_ignores(tmp_path: Path):
    _build_tree(tmp_path)
    assert has_file_with_extension(tmp_path, [".py"]) is True
    # The only .js file lives in node_modules, which is not part of the project.
    assert has_file_with_extension(tmp_path, [".js"]) is False
    assert has_file_with_extension(tmp_path, []) is False


def test_custom_ignore_list_replaces_the_default(tmp_path: Path):
    _build_tree(tmp_path)
    found = {p.name for p in iter_files(tmp_path, ignored_dirs={"src"})}
    assert "app.py" not in found
    assert "index.js" in found


def test_default_ignore_list_covers_common_build_output():
    for name in ("node_modules", ".git", "__pycache__", "dist", ".next", ".venv"):
        assert name in IGNORED_DIRS
