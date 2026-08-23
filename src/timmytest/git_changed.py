"""Git-aware changed-file detection and incremental (affected) test selection.

Enables ``timmytest run --changed`` / ``--since <ref>`` to execute only the
tests affected by recent code changes instead of the whole suite.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from timmytest.detector.gap_analyzer import _find_matching_test
from timmytest.detector.models import SourceModule, TestModule

#: git should answer a diff instantly; anything longer means it is blocked.
_GIT_TIMEOUT_SECONDS = 30


class NotAGitRepositoryError(RuntimeError):
    """Raised when incremental selection is requested outside a git repo."""


def get_changed_files(root: Path, ref: str | None = None) -> list[str]:
    """Return repo-relative paths of files changed vs ``ref`` (default: working tree + index vs HEAD).

    Includes untracked files (new source/test files count as "changed" for
    incremental runs). ``ref`` examples: ``HEAD~1``, ``main``, ``origin/main``,
    or a commit SHA.
    """
    # `--relative` makes git report paths relative to `root` rather than to the
    # repository root. Without it, auditing a subdirectory of a repo (a monorepo
    # package, or any project nested below its .git) produced paths that could
    # never match the scanner's module paths, so `--changed` silently selected
    # nothing and ran the entire suite.
    cmd = ["git", "diff", "--name-only", "--relative", ref if ref else "HEAD"]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # git not installed
        raise NotAGitRepositoryError("git is not available on this system") from exc
    except subprocess.TimeoutExpired as exc:
        # A held index.lock or a stalled credential prompt must not hang the audit.
        raise NotAGitRepositoryError(f"git did not respond within {_GIT_TIMEOUT_SECONDS}s") from exc

    if proc.returncode != 0:
        raise NotAGitRepositoryError(
            f"git diff failed (are you in a git repository?): {proc.stderr.strip()[:200]}"
        )

    changed = {line for line in proc.stdout.splitlines() if line.strip()}
    changed.update(line for line in untracked.stdout.splitlines() if line.strip())
    return sorted(changed)


def _normalise(path: str) -> str:
    return path.replace("\\", "/")


def select_affected_tests(
    changed_files: list[str],
    source_modules: list[SourceModule],
    test_modules: list[TestModule],
) -> list[str]:
    """Map changed files to the test files that exercise them.

    A changed file that is itself a test file is run directly; a changed source
    file is mapped to its matching test file via the same correlation logic used
    by gap analysis. Deduplicates and returns repo-relative test paths.
    """
    changed = {_normalise(p) for p in changed_files}
    test_by_rel = {_normalise(t.rel_path): t for t in test_modules}

    affected: set[str] = set()

    # 1. Directly changed test files.
    for rel in changed:
        if rel in test_by_rel:
            affected.add(rel)

    # 2. Changed source files -> their matching tests.
    for src in source_modules:
        if _normalise(src.rel_path) in changed:
            match = _find_matching_test(src, test_modules)
            if match is not None:
                affected.add(_normalise(match.rel_path))

    return sorted(affected)


def get_affected_test_paths(
    root: Path,
    source_modules: list[SourceModule],
    test_modules: list[TestModule],
    ref: str | None = None,
) -> list[str]:
    """High-level helper: git diff + correlation -> affected test file paths."""
    changed = get_changed_files(root, ref)
    return select_affected_tests(changed, source_modules, test_modules)
