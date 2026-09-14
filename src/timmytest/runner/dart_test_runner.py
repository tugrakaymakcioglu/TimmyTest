"""Dart / Flutter test runner (`dart test` / `flutter test`)."""

import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess, split_command
from timmytest.runner.dart_runner import parse_dart_output


class DartRunner(BaseRunner):
    """Executes Dart/Flutter tests and parses the shared console reporter.

    `dart test` prints cumulative progress counters (`00:02 +3 -1:`) plus a
    final verdict; `flutter test` keeps the same shapes. Both are handled by
    :func:`parse_dart_output`. When nothing machine-readable comes back (a
    crashed run), the non-zero exit code is surfaced as a suite-level failure
    instead of fabricated per-test counts.
    """

    def can_handle(self, root_dir: Path) -> bool:
        return (root_dir / "pubspec.yaml").exists()

    def _command_for(
        self,
        root_dir: Path,
        framework: TestFramework,
        custom_cmd: str | None,
        filter_pattern: str | None,
        test_paths: list[str] | None,
    ) -> tuple[list[str], str]:
        """Build argv + display command for this run."""
        if custom_cmd:
            display = custom_cmd
            if test_paths:
                argv = split_command(custom_cmd)
                argv.extend(test_paths)
                return argv, " ".join(argv)
            return split_command(custom_cmd), display

        base = "flutter test" if framework == TestFramework.FLUTTER_TEST else "dart test"
        argv = split_command(base)
        if test_paths:
            argv.extend(test_paths)
        elif filter_pattern:
            # package:test accepts plain name substrings as positional filters.
            argv.append(filter_pattern)
        return argv, " ".join(argv)

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 120,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
        *,
        ecosystem: Ecosystem = Ecosystem.DART,
        framework: TestFramework = TestFramework.DART_TEST,
    ) -> TestRunResult:
        argv, display_cmd = self._command_for(root_dir, framework, custom_cmd, filter_pattern, test_paths)
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
                command=display_cmd,
                total=0,
                failed=1,
                duration_seconds=duration,
                exit_code=124,
                raw_output=f"Dart test execution timed out after {timeout_seconds}s.\n\n{raw_output}",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Dart test run exceeded {timeout_seconds}s limit",
                        traceback=raw_output[-1000:],
                        suggested_fix="Increase timeout via --timeout option.",
                    )
                ],
            )

        passed, failed, skipped, errors, failures = parse_dart_output(raw_output)
        total = passed + failed + skipped

        # A run that died before producing any readable output (missing SDK,
        # pub get never run, syntax error in a test) still deserves an honest
        # suite-level failure rather than silent zeros.
        if total == 0 and not failures and exit_code != 0:
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Dart Test Runner Error",
                    error_type="RunnerError",
                    message="No test results could be parsed; the runner failed before reporting.",
                    traceback=raw_output[:1000],
                    suggested_fix=(
                        "Verify the Dart/Flutter SDK is on PATH and dependencies resolve "
                        "(`dart pub get` or `flutter pub get`), then re-run."
                    ),
                )
            )

        return TestRunResult(
            ecosystem=ecosystem,
            framework=framework,
            command=display_cmd,
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
