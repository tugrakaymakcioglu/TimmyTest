"""Node / JavaScript / TypeScript test runner supporting Vitest, Jest, Mocha, and npm."""

import re
import subprocess
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner


class NodeRunner(BaseRunner):
    """Executes Node/JS/TS tests using npm, vitest, jest, etc."""

    def can_handle(self, root_dir: Path) -> bool:
        return (root_dir / "package.json").exists()

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
    ) -> TestRunResult:
        cmd = custom_cmd or "npm test"
        if filter_pattern and not custom_cmd:
            cmd = f'npm test -- -t "{filter_pattern}"'

        start_time = time.time()
        raw_output = ""
        exit_code = 0

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            raw_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            return TestRunResult(
                ecosystem=Ecosystem.NODE,
                framework=TestFramework.JEST,
                command=cmd,
                total=0,
                failed=1,
                exit_code=124,
                raw_output=f"Test execution timed out after {timeout_seconds} seconds.",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Node test run exceeded {timeout_seconds}s limit",
                        suggested_fix="Check for unresolved Promises or hanging server listeners.",
                    )
                ],
            )
        except Exception as e:
            raw_output = f"Execution error: {e}"
            exit_code = 1

        duration = round(time.time() - start_time, 2)
        passed, failed, skipped, failures = self._parse_node_output(raw_output)

        total = passed + failed + skipped
        if total == 0 and exit_code != 0:
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Node Test Execution Failed",
                    error_type="ExecutionError",
                    message="Failed to run tests via npm/npx. See raw output.",
                    traceback=raw_output[:1000],
                    suggested_fix="Run 'npm install' or check package.json 'scripts.test'.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.NODE,
            framework=TestFramework.VITEST if "vitest" in cmd.lower() else TestFramework.JEST,
            command=cmd,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            raw_output=raw_output,
            has_executed=True,
        )

    def _parse_node_output(self, output: str) -> tuple[int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        skipped = 0
        failures: list[FailureDetail] = []

        # Jest / Vitest "Tests: 2 failed, 8 passed, 10 total"
        test_summary = re.search(r"Tests:\s+(.*?)(?:\n|$)", output)
        if test_summary:
            line = test_summary.group(1)
            f_m = re.search(r"(\d+)\s+failed", line)
            p_m = re.search(r"(\d+)\s+passed", line)
            s_m = re.search(r"(\d+)\s+skipped|\s*(\d+)\s+todo", line)

            if f_m:
                failed = int(f_m.group(1))
            if p_m:
                passed = int(p_m.group(1))
            if s_m:
                skipped = int(s_m.group(1) or s_m.group(2))

        # Check for FAIL blocks
        fail_files = re.findall(r"FAIL\s+([^\n]+)", output)
        if not fail_files:
            fail_files = re.findall(r"✕\s+([^\n]+)", output)

        for f_name in fail_files:
            failures.append(
                FailureDetail(
                    test_name=f_name.strip(),
                    error_type="NodeTestFailure",
                    message="Test suite or case failed",
                    traceback="",
                    suggested_fix="Check Jest/Vitest assertion errors and mock implementations.",
                )
            )

        return passed, failed, skipped, failures
