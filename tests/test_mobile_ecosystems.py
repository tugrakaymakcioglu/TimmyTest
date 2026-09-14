"""Regression tests for the Kotlin / Dart / Android detection & runner fixes (v2.0.1).

Each test maps to a bug reproduced live on fixture projects before the fix:

1. Kotlin sources without a build file detected as UNKNOWN.
2. Dart sources without pubspec.yaml detected as UNKNOWN.
3. Flutter projects suggested `dart test`, which refuses Flutter-SDK deps.
4. `dart test` output parsed as a bogus "collection error" (1 failed / 0 total).
5. CamelCase test files (`UserTest.kt`) invisible to `_is_test_file` because the
   name was lowercased and then compared with a mixed-case suffix.
6. Gradle per-test console lines parsed by nobody - JVM runs reported 0/0.
7. Gap suggestions for Dart/Kotlin used the generic Python-style layout.
"""

from pathlib import Path

from timmytest.detector.models import Ecosystem
from timmytest.detector.scanner import _is_test_file, _parse_generic_test
from timmytest.registry.loader import detect_from_registry
from timmytest.runner.dart_runner import parse_dart_output
from timmytest.runner.generic_runner import _parse_gradle_output

# --- 1 & 2: extension fallbacks ---------------------------------------------

def test_kotlin_sources_without_build_file_are_kotlin(tmp_path: Path):
    (tmp_path / "Main.kt").write_text("fun main() {}\n", encoding="utf-8")
    eco, fw, cmd, _ = detect_from_registry(tmp_path)
    assert eco == "kotlin"
    assert fw == "kotlin_test"


def test_dart_sources_without_pubspec_are_dart(tmp_path: Path):
    (tmp_path / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    eco, fw, cmd, _ = detect_from_registry(tmp_path)
    assert eco == "dart"
    assert cmd == "dart test"


def test_java_sources_without_build_file_are_java(tmp_path: Path):
    (tmp_path / "App.java").write_text("class App {}\n", encoding="utf-8")
    eco, _, _, _ = detect_from_registry(tmp_path)
    assert eco == "java"


# --- 3: flutter command selection -------------------------------------------

def test_flutter_project_gets_flutter_test_command(tmp_path: Path):
    (tmp_path / "pubspec.yaml").write_text(
        "name: myapp\ndependencies:\n  flutter:\n    sdk: flutter\n",
        encoding="utf-8",
    )
    (tmp_path / ".flutter-plugins-dependencies").write_text("{}\n", encoding="utf-8")
    eco, fw, cmd, configs = detect_from_registry(tmp_path)
    assert eco == "dart"
    assert fw == "flutter_test"
    assert cmd == "flutter test"
    # The config file list must still be reported for the UI.
    assert "pubspec.yaml" in configs


# --- 4: dart/flutter output parsing ------------------------------------------

def test_parse_dart_output_all_passed():
    out = (
        "00:00 +0: loading test/main_test.dart\n"
        "00:01 +2: test/add works\n"
        "00:01 +3: All tests passed!"
    )
    passed, failed, skipped, errors, failures = parse_dart_output(out)
    assert (passed, failed, skipped, errors) == (3, 0, 0, 0)
    assert failures == []


def test_parse_dart_output_failure_names_and_message():
    out = (
        "00:00 +0: loading test/main_test.dart\n"
        "00:02 +0 -1: add works [E]\n"
        "  Expected: 4\n"
        "    Actual: 3\n"
        "00:02 +0 -1: Some tests failed."
    )
    passed, failed, skipped, errors, failures = parse_dart_output(out)
    assert (passed, failed, skipped) == (0, 1, 0)
    assert len(failures) == 1
    assert failures[0].test_name == "add works"
    assert failures[0].message == "Expected: 4"


def test_parse_dart_output_skipped_counter():
    p, f, s, e, _ = parse_dart_output("00:03 +10 ~3: Some tests skipped.")
    assert (p, f, s) == (10, 0, 3)


def test_parse_dart_output_bare_total_verdict():
    """Flutter's `(total: N)` verdict without counters is a pass count, not an error."""
    p, f, s, e, _ = parse_dart_output("All tests passed! (total: 45)")
    assert (p, f, s, e) == (45, 0, 0, 0)


def test_parse_dart_output_prose_does_not_poison_counters():
    """`-1:` inside prose must not be read as a counter token."""
    out = (
        "00:02 +4: loading\n"
        "  Expected: 4\n"
        "    Actual: 3\n"
        "00:03 +5: All tests passed!"
    )
    p, f, s, e, _ = parse_dart_output(out)
    assert (p, f, s) == (5, 0, 0)


def test_parse_dart_output_unparseable_reports_error_slot():
    p, f, s, e, failures = parse_dart_output("crash: no such directory")
    assert (p, f, s, e) == (0, 0, 0, 1)
    assert failures == []


# --- 5: case-insensitive CamelCase test file names ---------------------------

def test_is_test_file_camelcase_kotlin_swift_scala():
    # These were dead branches before: lowercase(name).endswith("Test.kt") is always False.
    assert _is_test_file(Path("src/UserTest.kt"), Path("."))
    assert _is_test_file(Path("src/UserTests.kt"), Path("."))
    assert _is_test_file(Path("ios/UserTests.swift"), Path("."))
    assert _is_test_file(Path("src/UserSpec.scala"), Path("."))


def test_is_test_file_snake_case_kotlin_and_negatives():
    assert _is_test_file(Path("src/user_test.kt"), Path("."))
    # Non-test sources must stay sources.
    assert not _is_test_file(Path("src/Main.kt"), Path("."))
    assert not _is_test_file(Path("lib/main.dart"), Path("."))
    assert not _is_test_file(Path("MainActivity.java"), Path("."))


def test_is_test_file_dot_t_requires_a_stem():
    assert _is_test_file(Path("perl_suite.t"), Path("."))
    assert not _is_test_file(Path(".t"), Path("."))


def test_parse_generic_test_extracts_flutter_widget_tests():
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    f = tmp / "widget_test.dart"
    f.write_text(
        "test('plain', () {});\ntestWidgets('pump screen', (tester) {});",
        encoding="utf-8",
    )
    tests, _, _ = _parse_generic_test(f)
    # The JS `test('...')` rule already catches 'plain'; testWidgets adds its own.
    assert tests == ["plain", "pump screen"]


# --- 6: gradle console parsing ------------------------------------------------

def test_parse_gradle_output_counts_per_test_results():
    sample = (
        "com.example.app.MainActivityTest > addition_isCorrect PASSED\n"
        "com.example.app.MainActivityTest > subtraction FAILED\n"
        "> Task :app:test FAILED\n"
        "BUILD FAILED in 2s\n"
    )
    passed, failed, skipped, failures = _parse_gradle_output(sample)
    assert (passed, skipped) == (1, 0)
    assert failed == 1
    assert failures[0].test_name == "com.example.app.MainActivityTest.subtraction"


def test_parse_gradle_output_quiet_run_stays_zero():
    """Quiet gradle runs list no per-test lines; counts must stay honest zeros."""
    p, f, s, fails = _parse_gradle_output("> Task :test\nBUILD SUCCESSFUL in 1s")
    assert (p, f, s, fails) == (0, 0, 0, [])


# --- 7: ecosystem-aware gap suggestions ----------------------------------------

def _source(rel: str, language: str):
    from timmytest.detector.models import SourceModule

    return SourceModule(rel_path=rel, abs_path=f"/proj/{rel}", language=language)


def test_suggested_paths_for_dart_kotlin_java_swift(tmp_path: Path):
    from timmytest.detector.gap_analyzer import _suggest_test_path

    src = _source("lib/main.dart", "dart")
    assert _suggest_test_path(src, Ecosystem.DART, False) == "test/main_test.dart"

    kt = _source("calculator.kt", "kt")
    assert _suggest_test_path(kt, Ecosystem.KOTLIN, False) == "src/test/kotlin/CalculatorTest.kt"

    jv = _source("Parser.java", "java")
    assert _suggest_test_path(jv, Ecosystem.JAVA, False) == "src/test/java/ParserTest.java"

    sw = _source("engine.swift", "swift")
    assert _suggest_test_path(sw, Ecosystem.SWIFT, False) == "Tests/engineTests.swift"
