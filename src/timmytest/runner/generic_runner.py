"""Generic / custom command test runner with safe execution."""

import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess, split_command


class GenericRunner(BaseRunner):
    """Fallback runner for custom test commands, Maven, Gradle, .NET, PHPUnit, and RSpec."""

    def can_handle(self, root_dir: Path) -> bool:
        return True

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
        *,
        ecosystem: Ecosystem = Ecosystem.GENERIC,
        framework: TestFramework = TestFramework.CUSTOM,
    ) -> TestRunResult:
        base_cmd = custom_cmd or "pytest"
        # Targeted paths are appended as argv entries rather than concatenated
        # into the string: a test path containing a space would otherwise be
        # re-split into two bogus arguments.
        argv = split_command(base_cmd)
        if test_paths:
            argv.extend(test_paths)
        cmd = " ".join(argv)
        start_time = time.time()

        exit_code, raw_output, is_timeout = execute_safe_subprocess(
            argv,
            cwd=root_dir,
            timeout_seconds=timeout_seconds,
        )
        duration = round(time.time() - start_time, 2)

        if is_timeout:
            return TestRunResult(
                ecosystem=ecosystem,
                framework=framework,
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

        # The generic runner cannot reliably parse Maven/Gradle/.NET/PHP/Ruby
        # output, so report counts honestly rather than fabricating "1 passed".
        return TestRunResult(
            ecosystem=ecosystem,
            framework=framework,
            command=cmd,
            total=0,
            passed=0,
            failed=1 if exit_code != 0 else 0,
            duration_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            raw_output=raw_output,
            has_executed=True,
        )
