"""Test Gap Analyzer - correlates source modules to test files with high precision and import verification."""

from dataclasses import dataclass
from pathlib import Path

from timmytest.detector.models import Ecosystem, Priority, SourceModule, TestGap, TestModule


def _import_targets_module(imp: str, source: SourceModule) -> bool:
    """Does an import statement plausibly refer to *this* source file?

    Matching on the module name alone is far too loose: a single
    ``from myapp.utils import x`` would then mark ``billing/utils.py``,
    ``auth/utils.py`` and every other ``utils.py`` in the repository as tested.
    The import's dotted path is compared against the source file's own directory
    chain, so the match has to agree on *where* the module lives, not just what
    it is called.
    """
    src_path = Path(source.rel_path)
    module_name = src_path.stem
    normalised = imp.replace("/", ".").replace("\\", ".").lstrip(".")
    parts = [p for p in normalised.split(".") if p]
    if module_name not in parts:
        return False
    # `from pkg.mod import thing` — everything after the module name is a symbol.
    prefix = [p.lower() for p in parts[: parts.index(module_name)]]

    # Import paths are written relative to the import root, so a leading src/,
    # lib/ or app/ in the file path has no counterpart in the import statement.
    src_dirs = [p.lower() for p in src_path.parts[:-1]]
    while src_dirs and src_dirs[0] in {"src", "lib", "app"}:
        src_dirs.pop(0)

    if not prefix:
        # A bare `import utils` only names a module at the import root.
        return not src_dirs

    for start in range(len(src_dirs) - len(prefix) + 1):
        if src_dirs[start : start + len(prefix)] == prefix:
            return True
    return False


@dataclass(frozen=True)
class _PreparedTest:
    """A test module with its name/path facts computed once.

    Correlation is O(sources x tests); deriving the same stems and parent-name
    sets from scratch inside that loop meant re-parsing every test path once per
    source file - thousands of redundant ``Path`` builds on a normal repo.
    """

    module: TestModule
    stem: str
    clean_stem: str
    parent_names: frozenset[str]
    usable: bool


def _prepare_tests(test_modules: list[TestModule]) -> list[_PreparedTest]:
    prepared: list[_PreparedTest] = []
    for test in test_modules:
        test_path = Path(test.rel_path)
        stem = test_path.stem.lower()
        clean_stem = (
            stem.removeprefix("test_")
            .removesuffix("_test")
            .removesuffix(".test")
            .removesuffix(".spec")
            .removesuffix("_spec")
        )
        # A file picked up only because it sits inside a test directory, whose
        # name carries no test marker and which declares no test functions, is a
        # fixture or helper. `tests/helpers.py` must not be accepted as the test
        # suite for `src/helpers.py`. The name check keeps this safe for the
        # languages whose test functions the scanner cannot parse.
        named_like_test = "test" in stem or "spec" in stem
        prepared.append(
            _PreparedTest(
                module=test,
                stem=stem,
                clean_stem=clean_stem,
                parent_names=frozenset(p.lower() for p in test_path.parts[:-1]),
                usable=bool(test.test_functions) or named_like_test,
            )
        )
    return prepared


def _find_matching_test(
    source: SourceModule,
    test_modules: list[TestModule],
    prepared: list[_PreparedTest] | None = None,
) -> TestModule | None:
    """
    Find if a source module has a corresponding test file using exact naming,
    relative path mirroring, or AST import verification.

    ``prepared`` lets a caller correlating many sources hoist the per-test
    derivation out of its loop; it is computed on demand otherwise.
    """
    src_path = Path(source.rel_path)
    src_stem = src_path.stem.lower()
    src_stem_parts = src_stem.split("_")
    src_parent_names = {p.lower() for p in src_path.parts[:-1]}

    for entry in prepared if prepared is not None else _prepare_tests(test_modules):
        if not entry.usable:
            continue

        test_stem = entry.stem
        test_clean_stem = entry.clean_stem

        # 1. Exact stem match: e.g. test_auth.py or auth_test.py or auth.test.ts matches auth.py
        if (
            test_stem == f"test_{src_stem}"
            or test_stem == f"{src_stem}_test"
            or test_stem == f"{src_stem}.test"
            or test_stem == f"{src_stem}.spec"
            or test_stem == f"{src_stem}_spec"
            or test_stem == src_stem
            or test_clean_stem == src_stem
        ):
            return entry.module

        # 2. Path mirroring match: e.g. src/api/user.py -> tests/api/test_user.py
        if (
            src_stem in test_clean_stem.split("_") or test_clean_stem in src_stem_parts
        ) and src_parent_names.intersection(entry.parent_names) - {"src", "lib", "app"}:
            return entry.module

        # 3. Import verification: check if test imports this exact module
        if any(_import_targets_module(imp, source) for imp in entry.module.imported_modules):
            return entry.module

    return None


def _determine_priority(source: SourceModule) -> Priority:
    """Determine test priority for an untested source module."""
    if source.is_route or source.is_entrypoint:
        return Priority.HIGH
    if len(source.classes) >= 1 or len(source.functions) >= 3 or source.line_count >= 80:
        return Priority.HIGH
    if source.is_utility or source.is_model or len(source.functions) >= 1:
        return Priority.MEDIUM
    return Priority.LOW


def _suggest_test_path(source: SourceModule, ecosystem: Ecosystem, root_has_tests_dir: bool) -> str:
    """Suggest an appropriate test file path based on ecosystem conventions."""
    src_path = Path(source.rel_path)
    stem = src_path.stem

    if ecosystem == Ecosystem.PYTHON:
        if root_has_tests_dir:
            return f"tests/test_{stem}.py"
        return f"test_{stem}.py"
    elif ecosystem == Ecosystem.NODE:
        if root_has_tests_dir:
            return f"tests/{stem}.test.{source.language}"
        return f"{src_path.parent}/{stem}.test.{source.language}"
    elif ecosystem == Ecosystem.GO:
        return f"{src_path.parent}/{stem}_test.go"
    elif ecosystem == Ecosystem.RUST:
        return f"tests/{stem}_test.rs"
    elif ecosystem == Ecosystem.PHP:
        return f"tests/{stem.capitalize()}Test.php"
    elif ecosystem == Ecosystem.RUBY:
        return f"spec/{stem}_spec.rb"
    else:
        return f"tests/test_{stem}.{source.language}"


def analyze_test_gaps(
    source_modules: list[SourceModule],
    test_modules: list[TestModule],
    ecosystem: Ecosystem,
    root_dir: Path,
) -> tuple[list[TestGap], float]:
    """
    Analyzes which source modules are missing tests, assigns priorities,
    and calculates a test readiness score (0.0 - 100.0).
    """
    gaps: list[TestGap] = []
    has_tests_dir = (
        (root_dir / "tests").is_dir() or (root_dir / "__tests__").is_dir() or (root_dir / "spec").is_dir()
    )

    covered_count = 0
    total_sources = len(source_modules)

    if total_sources == 0:
        return [], 100.0

    prepared_tests = _prepare_tests(test_modules)

    for src in source_modules:
        matching_test = _find_matching_test(src, test_modules, prepared_tests)
        if matching_test:
            covered_count += 1
        else:
            priority = _determine_priority(src)
            suggested_path = _suggest_test_path(src, ecosystem, has_tests_dir)

            reasons: list[str] = []
            if src.is_route:
                reasons.append("API endpoint / route handler without integration tests")
            if src.is_entrypoint:
                reasons.append("Entry point without CLI / execution test")
            if src.classes:
                reasons.append(f"Classes without unit tests: {', '.join(src.classes)}")
            if src.functions:
                reasons.append(f"Functions without test coverage: {', '.join(src.functions[:4])}")
            if not reasons:
                reasons.append(f"Source file with {src.line_count} lines of untested code")

            reason_str = " | ".join(reasons)

            gaps.append(
                TestGap(
                    source_module=src.rel_path,
                    suggested_test_file=suggested_path,
                    priority=priority,
                    reason=reason_str,
                    functions_to_test=src.functions,
                    function_details=src.function_details,
                    classes_to_test=src.classes,
                )
            )

    # Sort gaps: HIGH first, then MEDIUM, then LOW
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    gaps.sort(key=lambda g: priority_order.get(g.priority, 3))

    # Calculate weighted readiness score
    if total_sources > 0:
        base_coverage = (covered_count / total_sources) * 100.0
        # Penalty for high priority gaps
        high_gaps = sum(1 for g in gaps if g.priority == Priority.HIGH)
        penalty = min(high_gaps * 5.0, 30.0)
        readiness_score = max(0.0, round(base_coverage - (penalty if covered_count > 0 else 0), 1))
        if covered_count == 0:
            readiness_score = 0.0
    else:
        readiness_score = 100.0

    return gaps, readiness_score
