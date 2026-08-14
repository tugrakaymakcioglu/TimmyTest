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
    assert res.passed == 1
    assert res.failed == 0

