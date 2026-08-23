"""Go test runner using go test with safe execution."""

import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess


class GoRunner(BaseRunner):
    """Executes Go tests using go test ./... with zero shell injection."""

    def can_handle(self, root_dir: Path) -> bool:
        return (root_dir / "go.mod").exists() or any(root_dir.glob("*.go"))

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
    ) -> TestRunResult:
        cmd_target: list[str] | str
        if custom_cmd:
            if test_paths:
                import shlex

                parts = shlex.split(custom_cmd)
                parts.extend(test_paths)
                cmd_target = parts
                display_cmd = " ".join(parts)
            else:
                cmd_target = custom_cmd
                display_cmd = custom_cmd
        else:
            args = ["go", "test", "-v"]
            if filter_pattern:
                args.extend(["-run", filter_pattern])
            if test_paths:
                args.extend(test_paths)
            else:
                args.append("./...")
            cmd_target = args
            display_cmd = " ".join(args)

        start_time = time.time()
        exit_code, raw_output, is_timeout = execute_safe_subprocess(
            cmd_target,
            cwd=root_dir,
            timeout_seconds=timeout_seconds,
        )
        duration = round(time.time() - start_time, 2)

        if is_timeout:
            return TestRunResult(
                ecosystem=Ecosystem.GO,
                framework=TestFramework.GO_TEST,
                command=display_cmd,
                total=0,
                failed=1,
                duration_seconds=duration,
                exit_code=124,
                raw_output=f"Go test execution timed out after {timeout_seconds}s.\n\n{raw_output}",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Go test exceeded {timeout_seconds}s limit",
                        traceback=raw_output[-1000:],
                        suggested_fix="Check for blocking channels or deadlocks.",
                    )
                ],
            )

        passed, failed, skipped, failures = self._parse_go_output(raw_output)

        total = passed + failed + skipped
        if total == 0 and exit_code != 0:
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Go Build/Test Failure",
                    error_type="GoError",
                    message="Go test execution returned non-zero exit code.",
                    traceback=raw_output[:1000],
                    suggested_fix="Check Go package compilation and imports.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.GO,
            framework=TestFramework.GO_TEST,
            command=display_cmd,
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

    def _parse_go_output(self, output: str) -> tuple[int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        skipped = 0
        failures: list[FailureDetail] = []

        for line in output.splitlines():
            if line.startswith("--- PASS:"):
                passed += 1
            elif line.startswith("--- FAIL:"):
                failed += 1
                t_name = line.replace("--- FAIL:", "").split()[0]
                failures.append(
                    FailureDetail(
                        test_name=t_name,
                        error_type="GoTestFail",
                        message="Go test assertion failed",
                        suggested_fix="Review t.Errorf / t.Fatalf statements in test function.",
                    )
                )
            elif line.startswith("--- SKIP:"):
                skipped += 1

        return passed, failed, skipped, failures
