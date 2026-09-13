"""Failures that must not be reported as complete test coverage."""

from timmytest import analysis
from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import Ecosystem, SourceModule, TestFramework, TestModule, TestRunResult
from timmytest.detector.scanner import scan_project_structure


def test_empty_project_has_no_readiness_evidence(tmp_path):
    assert analyze_test_gaps([], [], Ecosystem.PYTHON, tmp_path) == ([], 0.0)


def test_empty_named_test_does_not_cover_source(tmp_path):
    source = SourceModule(rel_path="src/payments.py", abs_path="", language="py")
    test = TestModule(rel_path="tests/test_payments.py", abs_path="", framework=TestFramework.PYTEST)
    gaps, score = analyze_test_gaps([source], [test], Ecosystem.PYTHON, tmp_path)
    assert [gap.source_module for gap in gaps] == ["src/payments.py"]
    assert score == 0.0


def test_duplicate_stems_need_import_evidence(tmp_path):
    sources = [
        SourceModule(rel_path="auth/utils.py", abs_path="", language="py"),
        SourceModule(rel_path="billing/utils.py", abs_path="", language="py"),
    ]
    test = TestModule(
        rel_path="tests/test_utils.py", abs_path="", framework=TestFramework.PYTEST,
        test_functions=["test_format"], imported_modules=["auth.utils"],
    )
    gaps, score = analyze_test_gaps(sources, [test], Ecosystem.PYTHON, tmp_path)
    assert [gap.source_module for gap in gaps] == ["billing/utils.py"]
    assert score < 100


def test_registry_patterns_find_java_integration_test(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Main.java").write_text("class Main {}", encoding="utf-8")
    (tmp_path / "src" / "MainIT.java").write_text("class MainIT {}", encoding="utf-8")
    _, tests = scan_project_structure(tmp_path, Ecosystem.JAVA, TestFramework.MAVEN)
    assert [test.rel_path for test in tests] == ["src/MainIT.java"]


def test_node_modern_extensions_are_scanned(tmp_path):
    (tmp_path / "widget.vue").write_text("<script>export default {}</script>", encoding="utf-8")
    (tmp_path / "widget.test.mjs").write_text('test("widget", () => {})', encoding="utf-8")
    sources, tests = scan_project_structure(tmp_path, Ecosystem.NODE, TestFramework.VITEST)
    assert [source.rel_path for source in sources] == ["widget.vue"]
    assert [test.rel_path for test in tests] == ["widget.test.mjs"]


def test_command_runs_even_without_discovered_test_file(monkeypatch, tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="sample"\nversion="0.1.0"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("#[cfg(test)] mod tests { #[test] fn works() {} }", encoding="utf-8")
    called = []
    monkeypatch.setattr(analysis, "run_project_tests", lambda **kwargs: called.append(kwargs) or TestRunResult(ecosystem=Ecosystem.RUST, framework=TestFramework.CARGO, command="cargo test", total=0, has_executed=True))
    monkeypatch.setattr(analysis, "enrich_test_failures", lambda result: result)
    analysis.analyze_project(tmp_path, execute_tests=True)
    assert len(called) == 1


def test_rust_inline_test_is_both_source_and_test(tmp_path):
    (tmp_path / "lib.rs").write_text(
        "pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
        "#[cfg(test)] mod tests { #[test]\nfn adds() { assert_eq!(super::add(1, 2), 3); } }",
        encoding="utf-8",
    )
    sources, tests = scan_project_structure(tmp_path, Ecosystem.RUST, TestFramework.CARGO)
    assert [source.rel_path for source in sources] == ["lib.rs"]
    assert [test.rel_path for test in tests] == ["lib.rs"]
    assert tests[0].test_functions == ["adds"]
