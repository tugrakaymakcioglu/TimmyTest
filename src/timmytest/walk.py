"""Directory traversal shared by the scanner, the detection registry and watch mode.

Every part of TimmyTest that touches the filesystem needs the same answer to
"what is not worth looking at": dependency trees, build output and VCS
internals. Keeping the list - and the pruning walk that uses it - in one
dependency-free module stops the three call sites from drifting apart, and
stops any of them from paying for a full ``node_modules`` traversal.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".github",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "bower_components",
    ".pnpm-store",
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    "vendor",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".coverage",
    "coverage",
    "htmlcov",
    ".idea",
    ".vscode",
    ".gradle",
    ".turbo",
    ".cache",
    ".parcel-cache",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".angular",
    ".terraform",
    ".timmytest",
}


def walk_dirs(root: Path, ignored_dirs: Iterable[str] | None = None) -> Iterator[tuple[str, list[str]]]:
    """Walk ``root`` yielding ``(dirpath, filenames)``, never entering ignored dirs.

    ``Path.rglob`` descends into every directory and filters afterwards, so a
    repository with a dependency tree pays for tens of thousands of stat calls it
    then discards. ``os.walk`` allows the directory list to be pruned in place,
    before those directories are ever opened.
    """
    ignored = set(IGNORED_DIRS if ignored_dirs is None else ignored_dirs)
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in ignored]
        yield dirpath, filenames


def iter_files(root: Path, ignored_dirs: Iterable[str] | None = None) -> Iterator[Path]:
    """Yield every file under ``root``, skipping ignored directories."""
    for dirpath, filenames in walk_dirs(root, ignored_dirs):
        current = Path(dirpath)
        for filename in filenames:
            yield current / filename


def has_file_with_extension(
    root: Path,
    extensions: Iterable[str],
    ignored_dirs: Iterable[str] | None = None,
) -> bool:
    """True as soon as one file with any of ``extensions`` is found.

    Short-circuits: the callers only ever need existence, and materialising the
    full match list of e.g. ``*.c`` across a monorepo to then check truthiness
    is the difference between microseconds and minutes.
    """
    suffixes = tuple(extensions)
    if not suffixes:
        return False
    for _dirpath, filenames in walk_dirs(root, ignored_dirs):
        for filename in filenames:
            if filename.endswith(suffixes):
                return True
    return False
