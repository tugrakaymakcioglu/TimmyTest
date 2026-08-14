"""End-to-end runner tests that execute real test suites in subprocesses.

These validate the runners against actual Go and Node projects (no mocks),
catching output-parsing regressions that unit tests cannot. Skipped when the
corresponding toolchain (``go`` / ``node`` / ``npm``) is unavailable.
"""

import shutil
from pathlib import Path

import pytest

from timmytest.runner.go_runner import GoRunner
from timmytest.runner.node_runner import NodeRunner

pytestmark = pytest.mark.skipif(
    shutil.which("go") is None and shutil.which("node") is None and shutil.which("npm") is None,
    reason="go/node/npm toolchain not available",
)


def _write_go_project(root: Path) -> None:
    (root / "go.mod").write_text("module example.com/math\n\ngo 1.21\n", encoding="utf-8")
    (root / "math.go").write_text(
        "package math\n\nfunc Add(a, b int) int { return a + b }\n", encoding="utf-8"
    )
    (root / "math_test.go").write_text(
        "package math\n\nimport \"testing\"\n\n"
        "func TestAdd(t *testing.T) {\n\tif Add(2, 3) != 5 {\n\t\tt.Fatalf(\"expected 5, got %d\", Add(2, 3))\n\t}\n}\n",
        encoding="utf-8",
    )


def _write_node_project(root: Path) -> None:
    (root / "package.json").write_text(
        '{"name":"demo","version":"1.0.0","scripts":{"test":"node --test"}}',
        encoding="utf-8",
    )
    (root / "math.test.js").write_text(
        "const { test } = require('node:test');\n"
        "const assert = require('node:assert');\n"
        "test('add works', () => { assert.strictEqual(2 + 3, 5); });\n"
        "test('subtract works', () => { assert.strictEqual(5 - 2, 3); });\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(shutil.which("go") is None, reason="go toolchain not available")
def test_go_runner_executes_real_project(tmp_path):
    _write_go_project(tmp_path)
    result = GoRunner().run_tests(tmp_path, timeout_seconds=120)
    assert result.has_executed is True
    assert result.exit_code == 0
    assert result.passed == 1
    assert result.failed == 0
    assert result.total == 1


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node toolchain not available",
)
def test_node_runner_executes_real_project(tmp_path):
    # Invoke `node --test` directly rather than `npm test`: the latter spawns a
    # nested cmd.exe whose PATH resolution of `node` is broken on some Windows
    # setups (a machine/environment issue, not a code issue). The point of this
    # test is real subprocess execution + TAP parsing, which `node --test`
    # exercises identically.
    _write_node_project(tmp_path)
    result = NodeRunner().run_tests(tmp_path, custom_cmd="node --test", timeout_seconds=120)
    assert result.has_executed is True
    assert result.exit_code == 0
    # TAP output from node --test must be parsed.
    assert result.passed == 2
    assert result.failed == 0
    assert result.total == 2


def test_node_runner_parses_tap_output():
    runner = NodeRunner()
    sample = (
        "TAP version 13\n"
        "ok 1 - add works\n"
        "not ok 2 - broken test\n"
        "1..2\n"
        "# tests 2\n"
        "# pass 1\n"
        "# fail 1\n"
        "# skipped 0\n"
        "# todo 0\n"
    )
    passed, failed, skipped, failures = runner._parse_node_output(sample)
    assert passed == 1
    assert failed == 1
    assert skipped == 0
    assert len(failures) == 1
    assert "broken test" in failures[0].test_name
