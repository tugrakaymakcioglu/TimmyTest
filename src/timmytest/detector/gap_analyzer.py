"""Test Gap Analyzer - correlates source modules to test files and scores readiness."""

from pathlib import Path

from timmytest.detector.models import Ecosystem, Priority, SourceModule, TestGap, TestModule


def _find_matching_test(source: SourceModule, test_modules: list[TestModule]) -> TestModule | None:
    """Find if a source module has a corresponding test file."""
    src_path = Path(source.rel_path)
    src_stem = src_path.stem.lower()
    src_parts = [p.lower() for p in src_path.parts]

    for test in test_modules:
        test_path = Path(test.rel_path)
        test_stem = test_path.stem.lower()
        test_clean_stem = (
            test_stem.removeprefix("test_").removesuffix("_test").removesuffix(".test").removesuffix(".spec")
        )

        # 1. Exact match e.g. test_auth matches auth.py
        if (
            test_stem == f"test_{src_stem}"
            or test_stem == f"{src_stem}_test"
            or test_stem == f"{src_stem}.test"
            or test_stem == f"{src_stem}.spec"
            or test_stem == src_stem
            or test_clean_stem == src_stem
        ):
            return test

        # 2. Package / subfolder match e.g. test_detector matches src/timmytest/detector/ecosystem.py
        # or test_runners matches src/timmytest/runner/python_runner.py
        for part in src_parts:
            part_clean = part.removesuffix(".py").removesuffix(".ts").removesuffix(".js")
            if part_clean in {test_clean_stem, test_clean_stem.rstrip("s"), f"{test_clean_stem}s"}:
                return test

        # 3. Stem in test name or vice-versa
        if src_stem in test_stem or (len(test_clean_stem) > 3 and test_clean_stem in src_stem):
            return test

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
    has_tests_dir = (root_dir / "tests").is_dir() or (root_dir / "__tests__").is_dir()

    covered_count = 0
    total_sources = len(source_modules)

    if total_sources == 0:
        return [], 100.0

    for src in source_modules:
        matching_test = _find_matching_test(src, test_modules)
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
