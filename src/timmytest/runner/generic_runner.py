"""Generic / custom command test runner with safe execution."""

import re
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess, split_command

# `gradle test` / `./gradlew test` console output (testLogging events on):
#   com.example.AppTest > addition_isCorrect PASSED
#   com.example.AppTest > subtraction FAILED
# Quiet runs print only the task line; failures end with
#   > Task :app:test FAILED
#   BUILD FAILED in 3s
_GRADLE_RESULT_RE = re.compile(
    r"^(?P<cls>\S[^\n>]*?)\s*>\s*(?P<method>\S+)\s+(?P<status>PASSED|FAILED|SKIPPED)\s*$",
    re.MULTILINE,
)
_GRADLE_TASK_FAILED_RE = re.compile(r"^>\s+Task\s+:.*:test\b.*FAILED\s*$", re.MULTILINE)


def _parse_gradle_output(raw_output: str) -> tuple[int, int, int, list[FailureDetail]]:
    """Parse per-test PASSED/FAILED/SKIPPED lines from a Gradle run.

    Returns ``(passed, failed, skipped, failures)``. Counts stay zero when the
    console never lists individual tests (the default for quiet runs); callers
    must then report honestly rather than invent numbers.
    """
    passed = failed = skipped = 0
    failures: list[FailureDetail] = []
    seen_failed: set[str] = set()

    for match in _GRADLE_RESULT_RE.finditer(raw_output):
        cls, method = match.group("cls"), match.group("method")
        status = match.group("status")
        if status == "PASSED":
            passed += 1
        elif status == "SKIPPED":
            skipped += 1
        else:
            failed += 1
            failure_key = f"{cls.strip()}.{method}"
            if failure_key not in seen_failed:
                seen_failed.add(failure_key)
                # Keep `Class.method` so the failure stays attributable even when
                # Gradle prints no stack trace to the console.
                failures.append(
                    FailureDetail(
                        test_name=f"{cls.strip()}.{method}",
                        error_type="TestFailure",
                        message="Gradle reported this test as FAILED.",
                        suggested_fix="Run `./gradlew test --info` or open the HTML report for the stack trace.",
                    )
                )
    return passed, failed, skipped, failures


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
                duration_seconds=duration,
                exit_code=124,
                raw_output=f"Execution timed out after {timeout_seconds} seconds.\n\n{raw_output}",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Test command timed out after {timeout_seconds}s",
                        traceback=raw_output[-1000:],
                        suggested_fix="Increase timeout via --timeout option.",
                    )
                ],
            )

        failures: list[FailureDetail] = []
        total = passed = failed = skipped = errors = 0

        # JVM/Gradle ecosystems get real per-test counts when the console lists
        # them; every other generic command stays honest with zeros.
        if framework in (TestFramework.GRADLE, TestFramework.KOTLIN_TEST) or ecosystem in (
            Ecosystem.JAVA,
            Ecosystem.KOTLIN,
        ):
            passed, failed, skipped, gradle_failures = _parse_gradle_output(raw_output)
            failures.extend(gradle_failures)
            total = passed + failed + skipped

        if exit_code != 0 and not failures:
            failures.append(
                FailureDetail(
                    test_name="Command Failed",
                    error_type="ExitCodeNonZero",
                    message=f"Command '{cmd}' exited with code {exit_code}.",
                    traceback=raw_output[:1000],
                    suggested_fix="Review command output and verify test dependencies.",
                )
            )
            # The command itself broke before tests could report; surface one
            # suite-level failure instead of pretending a test failed.
            if total == 0:
                failed = 1
            else:
                errors = 1

        return TestRunResult(
            ecosystem=ecosystem,
            framework=framework,
            command=cmd,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            raw_output=raw_output,
            has_executed=True,
        )
