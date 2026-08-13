"""Tests for test runner parsers."""

from timmytest.runner.go_runner import GoRunner
from timmytest.runner.node_runner import NodeRunner
from timmytest.runner.python_runner import PythonRunner
from timmytest.runner.rust_runner import RustRunner


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


def test_node_runner_parse_jest_output():
    runner = NodeRunner()
    sample_output = """
FAIL src/auth.test.ts
  ● Auth › should reject invalid password
    expect(received).toBe(expected) // Object.is equality
    Expected: 401
    Received: 403

Tests:       1 failed, 4 passed, 5 total
"""
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
