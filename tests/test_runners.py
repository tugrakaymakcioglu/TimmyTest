"""Tests for test runner parsers, safe execution, and ANSI cleaning."""

from pathlib import Path

from timmytest.detector.models import Ecosystem, TestFramework
from timmytest.runner.base import strip_ansi
from timmytest.runner.go_runner import GoRunner
from timmytest.runner.node_runner import NodeRunner
from timmytest.runner.orchestrator import run_project_tests
from timmytest.runner.python_runner import PythonRunner
from timmytest.runner.rust_runner import RustRunner


def test_strip_ansi():
    colored_text = "\x1b[32mPASS\x1b[0m \x1b[1mtests/auth.test.ts\x1b[0m"
    clean = strip_ansi(colored_text)
    assert clean == "PASS tests/auth.test.ts"


def test_python_runner_parse_pytest_output():
    runner = PythonRunner()
    sample_output = """
============================= test session starts =============================
tests/test_auth.py::test_login PASSED                                    [ 33%]
tests/test_auth.py::test_bad_pass FAILED                                 [ 66%]
tests/test_auth.py::test_skip SKIPPED                                    [100%]

=================================== FAILURES ===================================
________________________________ test_bad_pass _________________________________
tests/test_auth.py:42: in test_bad_pass
    assert res.status_code == 401
E   AssertionError: assert 403 == 401
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_bad_pass - AssertionError: assert 403 == 401
==================== 1 failed, 1 passed, 1 skipped in 0.15s ====================
"""
    passed, failed, skipped, errors, failures = runner._parse_pytest_output(sample_output)

    assert passed == 1
    assert failed == 1
    assert skipped == 1
    assert len(failures) == 1
    assert failures[0].test_name == "test_bad_pass"
    assert failures[0].line_number == 42
    assert "assert 403 == 401" in failures[0].message


def test_node_runner_parse_jest_output_with_ansi():
    runner = NodeRunner()
    sample_output = strip_ansi("""
\x1b[31mFAIL\x1b[0m src/auth.test.ts
  ● Auth › should reject invalid password
    expect(received).toBe(expected) // Object.is equality
    Expected: 401
    Received: 403

\x1b[1mTests:       1 failed, 4 passed, 5 total\x1b[0m
""")
    passed, failed, skipped, failures = runner._parse_node_output(sample_output)

    assert passed == 4
    assert failed == 1
    assert len(failures) == 1
    assert "auth.test.ts" in failures[0].test_name


def test_node_runner_parse_vitest_summary():
    """Vitest writes 'Tests  N passed (N)' - no colon, pipes instead of commas."""
    runner = NodeRunner()
    sample = """
 RUN  v4.0.18 C:/projects/app

 ✓ __tests__/lib/security.test.js (26 tests) 16ms

 Test Files  4 passed (4)
      Tests  1 failed | 71 passed | 2 skipped (74)
   Start at  15:41:11
   Duration  24.55s
"""
    passed, failed, skipped, failures = runner._parse_node_output(sample)

    assert passed == 71
    assert failed == 1
    assert skipped == 2


def test_node_runner_counts_failed_suite_as_error():
    """A suite that fails to load leaves every test green; the run is still broken."""
    runner = NodeRunner()
    sample = """
 ❯ tests/example.spec.ts (0 test)

 Test Files  1 failed | 4 passed (5)
      Tests  72 passed (72)

 FAIL  tests/example.spec.ts [ tests/example.spec.ts ]
Error: Playwright Test did not expect test() to be called here.
"""
    passed, failed, skipped, failures = runner._parse_node_output(sample)
    assert (passed, failed, skipped) == (72, 0, 0)
    assert runner._parse_failed_suites(sample) == 1
    # The FAIL line is emitted twice by Vitest in a real run; only one failure.
    assert len(failures) == 1
    assert failures[0].test_name == "tests/example.spec.ts"


def test_node_runner_parse_mocha_output():
    runner = NodeRunner()
    sample = "\n  72 passing (2s)\n  1 failing\n  2 pending\n"
    passed, failed, skipped, _ = runner._parse_node_output(sample)
    assert (passed, failed, skipped) == (72, 1, 2)


def test_node_runner_jest_counts_todo_and_skipped():
    runner = NodeRunner()
    sample = "Tests:       1 failed, 2 skipped, 3 todo, 4 passed, 10 total\n"
    passed, failed, skipped, _ = runner._parse_node_output(sample)
    assert (passed, failed, skipped) == (4, 1, 5)


def test_node_runner_appends_test_paths_without_stray_separator():
    runner = NodeRunner()
    assert runner._append_test_paths(["npm", "test"], ["a.test.js"]) == [
        "npm",
        "test",
        "--",
        "a.test.js",
    ]
    assert runner._append_test_paths(["node", "--test"], ["a.test.js"]) == [
        "node",
        "--test",
        "a.test.js",
    ]


def test_rust_runner_parse_cargo_output():
    runner = RustRunner()
    sample_output = """
running 3 tests
test tests::test_add ... ok
test tests::test_fail ... FAILED
test tests::test_ignored ... ignored

failures:

---- tests::test_fail stdout ----
thread 'tests::test_fail' panicked at src/lib.rs:15:9:
assertion `left == right` failed
  left: 4
 right: 5

failures:
    tests::test_fail

test result: FAILED. 1 passed; 1 failed; 1 ignored; 0 measured; 0 filtered out
"""
    passed, failed, ignored, failures = runner._parse_cargo_output(sample_output)

    assert passed == 1
    assert failed == 1
    assert ignored == 1
    assert len(failures) == 1
    assert "test_fail" in failures[0].test_name


def test_go_runner_parse_output():
    runner = GoRunner()
    sample_output = """
=== RUN   TestAdd
--- PASS: TestAdd (0.00s)
=== RUN   TestSubtract
--- FAIL: TestSubtract (0.00s)
=== RUN   TestIgnored
--- SKIP: TestIgnored (0.00s)
"""
    passed, failed, skipped, failures = runner._parse_go_output(sample_output)

    assert passed == 1
    assert failed == 1
    assert skipped == 1
    assert len(failures) == 1
    assert failures[0].test_name == "TestSubtract"


def test_orchestrator_multi_ecosystem(temp_project_dir: Path):
    import sys

    # Test Java project orchestration
    (temp_project_dir / "pom.xml").write_text("<project></project>", encoding="utf-8")
    py_exe = sys.executable
    result = run_project_tests(
        temp_project_dir,
        Ecosystem.JAVA,
        TestFramework.MAVEN,
        custom_cmd=f'"{py_exe}" -c "print(\'mvn_test_ran\')"',
    )
    assert result.has_executed is True
    assert "mvn_test_ran" in result.raw_output


def test_orchestrator_explicit_ecosystem_beats_can_handle(temp_project_dir: Path):
    """A Java project with a stray package.json must still route to Java, not Node."""
    (temp_project_dir / "pom.xml").write_text("<project></project>", encoding="utf-8")
    (temp_project_dir / "package.json").write_text("{}", encoding="utf-8")
    result = run_project_tests(
        temp_project_dir,
        Ecosystem.JAVA,
        TestFramework.MAVEN,
        timeout_seconds=30,
    )
    assert result.ecosystem == Ecosystem.JAVA
    assert result.command == "mvn test"


def test_orchestrator_unknown_ecosystem_sniffs(temp_project_dir: Path):
    """UNKNOWN ecosystem falls back to can_handle sniffing (Python via pyproject.toml)."""
    import sys

    (temp_project_dir / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    # Provide a pytest that exists on PATH for deterministic routing.
    result = run_project_tests(
        temp_project_dir,
        Ecosystem.UNKNOWN,
        TestFramework.UNKNOWN,
        custom_cmd=f'"{sys.executable}" -c "print(\'sniffed\')"',
    )
    assert result.has_executed is True


def test_python_runner_parse_pytest_quiet_mode():
    """`pytest -q` prints a bare summary with no `=` frame and no status lines.

    Both parsers used to come up empty, so an all-green quiet run was reported
    as 0 total - or, with a non-zero exit, as a bogus collection error.
    """
    runner = PythonRunner()
    passed, failed, skipped, errors, failures = runner._parse_pytest_output("2 passed in 0.01s")
    assert (passed, failed, skipped, errors) == (2, 0, 0, 0)
    assert failures == []

    passed, failed, skipped, errors, _ = runner._parse_pytest_output("4 failed, 2 passed, 1 skipped in 0.12s")
    assert (passed, failed, skipped, errors) == (2, 4, 1, 0)


def test_python_runner_resolves_unavailable_recommended_command(temp_project_dir: Path):
    """The registry's `pytest -ra` presumes a global pytest; without one the run
    used to die with WinError 2 / FileNotFoundError and report a bogus
    collection error instead of falling back to the smart resolver."""
    (temp_project_dir / "test_thing.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    runner = PythonRunner()
    # A binary name that cannot exist on any platform keeps this test honest on
    # machines that DO have pytest installed globally.
    res = runner.run_tests(
        temp_project_dir,
        custom_cmd="definitely-not-a-real-binary-9x7q -ra",
        timeout_seconds=120,
    )
    assert res.has_executed is True
    assert res.exit_code == 0
    assert res.passed == 1


def test_node_runner_failure_names_deduplicate_and_strip_decorations():
    names = NodeRunner()._failure_names(
        "FAIL  src/a.test.js [ 0.5s ]\n \u2715 divides (1 ms)\nFAIL  src/a.test.js"
    )
    assert names == ["src/a.test.js", "divides"]


def test_python_runner_runs_with_test_paths(temp_project_dir: Path):
    """Incremental test_paths targets a specific test file and executes it."""
    (temp_project_dir / "test_thing.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")
    result = PythonRunner().run_tests(temp_project_dir, test_paths=["test_thing.py"], timeout_seconds=60)
    assert result.has_executed is True
    assert result.passed == 1
    assert result.failed == 0


def test_generic_runner(temp_project_dir: Path):
    import sys

    from timmytest.runner.generic_runner import GenericRunner

    runner = GenericRunner()
    assert runner.can_handle(temp_project_dir) is True
    py_exe = sys.executable
    res = runner.run_tests(
        temp_project_dir,
        custom_cmd=f'"{py_exe}" -c "import sys; sys.exit(0)"',
    )
    assert res.has_executed is True
    # The generic runner cannot parse arbitrary command output, so it reports
    # counts honestly (0/0) instead of fabricating "1 passed".
    assert res.exit_code == 0
    assert res.passed == 0
    assert res.failed == 0

    # A failing generic command is reported as one failure, not fabricated pass.
    res_fail = runner.run_tests(
        temp_project_dir,
        custom_cmd=f'"{py_exe}" -c "import sys; sys.exit(1)"',
    )
    assert res_fail.has_executed is True
    assert res_fail.exit_code != 0
    assert res_fail.failed == 1
