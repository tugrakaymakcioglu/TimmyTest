"""Node / JavaScript / TypeScript test runner supporting Vitest, Jest, Mocha, pnpm, yarn, bun, and npm."""

import re
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess


class NodeRunner(BaseRunner):
    """Executes Node/JS/TS tests using pnpm, yarn, bun, npm, vitest, jest with zero shell injection."""

    def can_handle(self, root_dir: Path) -> bool:
        return (
            (root_dir / "package.json").exists()
            or (root_dir / "deno.json").exists()
            or (root_dir / "deno.jsonc").exists()
        )

    def _determine_node_cmd(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        filter_pattern: str | None = None,
    ) -> list[str]:
        if custom_cmd:
            return [custom_cmd]  # Will be parsed safely by execute_safe_subprocess

        # Detect package runner
        if (root_dir / "deno.json").exists() or (root_dir / "deno.jsonc").exists():
            args = ["deno", "test"]
            if filter_pattern:
                args.extend(["--filter", filter_pattern])
            return args

        runner = "npm"
        if (root_dir / "pnpm-lock.yaml").exists():
            runner = "pnpm"
        elif (root_dir / "yarn.lock").exists():
            runner = "yarn"
        elif (root_dir / "bun.lockb").exists() or (root_dir / "bun.lock").exists():
            runner = "bun"

        args = [runner, "test"]
        if filter_pattern:
            args.extend(["--", "-t", filter_pattern])
        return args

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
    ) -> TestRunResult:
        cmd_args = self._determine_node_cmd(root_dir, custom_cmd, filter_pattern)
        display_cmd = custom_cmd if custom_cmd else " ".join(cmd_args)

        # Append targeted test file paths for incremental runs.
        if test_paths:
            if custom_cmd:
                import shlex

                cmd_args = shlex.split(custom_cmd) + ["--", *test_paths]
            else:
                cmd_args.extend(["--", *test_paths])
            display_cmd = " ".join(cmd_args)

        start_time = time.time()
        exit_code, raw_output, is_timeout = execute_safe_subprocess(
            custom_cmd or cmd_args,
            cwd=root_dir,
            timeout_seconds=timeout_seconds,
        )
        duration = round(time.time() - start_time, 2)

        if is_timeout:
            return TestRunResult(
                ecosystem=Ecosystem.NODE,
                framework=TestFramework.JEST,
                command=display_cmd,
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

        passed, failed, skipped, failures = self._parse_node_output(raw_output)

        total = passed + failed + skipped
        if total == 0 and exit_code != 0:
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Node Test Execution Failed",
                    error_type="ExecutionError",
                    message="Failed to run tests via package manager. See raw output.",
                    traceback=raw_output[:1000],
                    suggested_fix="Run 'npm install' (or pnpm/yarn/bun) and check package.json 'scripts.test'.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.NODE,
            framework=TestFramework.VITEST if "vitest" in display_cmd.lower() else TestFramework.JEST,
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

        # Node's built-in test runner (node --test / TAP output):
        #   # tests 2  # pass 2  # fail 0  # skipped 0  # todo 0
        if passed == 0 and failed == 0:
            p_m = re.search(r"#\s*pass\s+(\d+)", output)
            f_m = re.search(r"#\s*fail\s+(\d+)", output)
            s_m = re.search(r"#\s*skipped\s+(\d+)", output)
            t_m = re.search(r"#\s*todo\s+(\d+)", output)
            if p_m or f_m:
                passed = int(p_m.group(1)) if p_m else 0
                failed = int(f_m.group(1)) if f_m else 0
                skipped = int(s_m.group(1)) if s_m else 0
                skipped += int(t_m.group(1)) if t_m else 0

        # Check for FAIL / ✕ blocks (Jest/Vitest).
        fail_files = re.findall(r"FAIL\s+([^\n]+)", output)
        if not fail_files:
            fail_files = re.findall(r"✕\s+([^\n]+)", output)

        # TAP failures: "not ok N - test name"
        if not fail_files:
            fail_files = re.findall(r"not ok\s+\d+\s*-\s*([^\n]+)", output)

        for f_name in fail_files:
            failures.append(
                FailureDetail(
                    test_name=f_name.strip(),
                    error_type="NodeTestFailure",
                    message="Test suite or case failed",
                    traceback="",
                    suggested_fix="Check Jest/Vitest/node:test assertion errors and mock implementations.",
                )
            )

        return passed, failed, skipped, failures
