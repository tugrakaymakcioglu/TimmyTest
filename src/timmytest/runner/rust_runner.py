"""Rust test runner using cargo test with safe execution."""

import re
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess


class RustRunner(BaseRunner):
    """Executes Rust tests via cargo test with zero shell injection."""

    def can_handle(self, root_dir: Path) -> bool:
        return (root_dir / "Cargo.toml").exists()

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 120,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
    ) -> TestRunResult:
        cmd_target: list[str] | str
        if custom_cmd:
            if test_paths:
                import shlex

                parts = shlex.split(custom_cmd)
                parts.append(Path(test_paths[0]).stem)
                cmd_target = parts
                display_cmd = " ".join(parts)
            else:
                cmd_target = custom_cmd
                display_cmd = custom_cmd
        else:
            args = ["cargo", "test"]
            if filter_pattern:
                args.append(filter_pattern)
            elif test_paths:
                # cargo test accepts a substring filter; use the first test file's stem.
                args.append(Path(test_paths[0]).stem)
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
                ecosystem=Ecosystem.RUST,
                framework=TestFramework.CARGO,
                command=display_cmd,
                total=0,
                failed=1,
                duration_seconds=duration,
                exit_code=124,
                raw_output=f"Cargo test execution timed out after {timeout_seconds}s.\n\n{raw_output}",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Rust test run exceeded {timeout_seconds}s limit",
                        traceback=raw_output[-1000:],
                        suggested_fix="Check for deadlocks or increase timeout.",
                    )
                ],
            )

        passed, failed, ignored, failures = self._parse_cargo_output(raw_output)

        total = passed + failed + ignored
        if total == 0 and exit_code != 0:
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Cargo Build/Test Error",
                    error_type="CargoError",
                    message="Compilation or test execution failed.",
                    traceback=raw_output[:1000],
                    suggested_fix="Fix compiler errors before running tests.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.RUST,
            framework=TestFramework.CARGO,
            command=display_cmd,
            total=total,
            passed=passed,
            failed=failed,
            skipped=ignored,
            duration_seconds=duration,
            exit_code=exit_code,
            failures=failures,
            raw_output=raw_output,
            has_executed=True,
        )

    def _parse_cargo_output(self, output: str) -> tuple[int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        ignored = 0
        failures: list[FailureDetail] = []

        # test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
        for line in output.splitlines():
            res_match = re.search(
                r"test result: (?:FAILED|ok)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored",
                line,
            )
            if res_match:
                passed += int(res_match.group(1))
                failed += int(res_match.group(2))
                ignored += int(res_match.group(3))

        # Parse failures list
        fail_matches = re.findall(r"----\s+([^\s]+)\s+stdout\s+----([\s\S]*?)(?:failures:|\Z)", output)
        for t_name, t_body in fail_matches:
            failures.append(
                FailureDetail(
                    test_name=t_name.strip(),
                    error_type="RustPanic",
                    message="Rust test panicked / assertion failed",
                    traceback=t_body.strip()[:600],
                    suggested_fix="Inspect panic location and assert_eq! macro values.",
                )
            )

        return passed, failed, ignored, failures
