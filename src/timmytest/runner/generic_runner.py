"""Generic / custom command test runner."""

import subprocess
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner


class GenericRunner(BaseRunner):
    """Fallback runner for custom test commands."""

    def can_handle(self, root_dir: Path) -> bool:
        return True

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
    ) -> TestRunResult:
        cmd = custom_cmd or "pytest"
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
                ecosystem=Ecosystem.GENERIC,
                framework=TestFramework.CUSTOM,
                command=cmd,
                total=0,
                failed=1,
                exit_code=124,
                raw_output=f"Execution timed out after {timeout_seconds} seconds.",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Test command timed out after {timeout_seconds}s",
                        suggested_fix="Increase timeout via --timeout option.",
                    )
                ],
            )
        except Exception as e:
            raw_output = f"Execution error: {e}"
            exit_code = 1

        duration = round(time.time() - start_time, 2)
        failures = []

        if exit_code != 0:
            failures.append(
                FailureDetail(
                    test_name="Command Failed",
                    error_type="ExitCodeNonZero",
                    message=f"Command '{cmd}' exited with code {exit_code}.",
                    traceback=raw_output[:1000],
                    suggested_fix="Review command output and verify test dependencies.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.GENERIC,
            framework=TestFramework.CUSTOM,
            command=cmd,
            total=1 if exit_code == 0 else 1,
            passed=1 if exit_code == 0 else 0,
            failed=0 if exit_code == 0 else 1,
            duration_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            raw_output=raw_output,
            has_executed=True,
        )
