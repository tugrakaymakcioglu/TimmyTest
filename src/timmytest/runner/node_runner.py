"""Node / JavaScript / TypeScript test runner supporting Vitest, Jest, Mocha, pnpm, yarn, bun, and npm."""

import re
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner, execute_safe_subprocess, split_command

PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun", "npx"}

# "Tests:  1 failed, 4 passed, 5 total"   (Jest, colon + commas)
# "      Tests  1 failed | 71 passed (72)" (Vitest, no colon + pipes)
TESTS_SUMMARY_RE = re.compile(r"^[^\S\n]*Tests:?[^\S\n]+(\S.*)$", re.MULTILINE)
# "  Test Files  1 failed | 4 passed (5)"  (Vitest, suite level)
TEST_FILES_SUMMARY_RE = re.compile(r"^[^\S\n]*Test Files:?[^\S\n]+(\S.*)$", re.MULTILINE)
COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|skipped|todo|pending)\b")
# Mocha: "  72 passing (2s)" / "  1 failing" / "  2 pending"
MOCHA_RE = re.compile(r"^\s*(\d+)\s+(passing|failing|pending)\b", re.MULTILINE)


def _counts_from_summary(line: str) -> dict[str, int]:
    """Turn a Jest/Vitest summary fragment into {kind: count}.

    Handles both separators the ecosystem uses - Jest's ``1 failed, 4 passed,
    5 total`` and Vitest's ``1 failed | 71 passed | 2 skipped (74)`` - because a
    single missing format here is the difference between a real report and a
    dashboard full of zeroes.
    """
    counts: dict[str, int] = {}
    for number, kind in COUNT_RE.findall(line):
        counts[kind] = counts.get(kind, 0) + int(number)
    return counts


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
            args = split_command(custom_cmd)
            # Only pass the name filter when the command is a runner that has
            # one; appending -t to e.g. `node --test` would abort the run.
            lowered = custom_cmd.lower()
            if filter_pattern and ("vitest" in lowered or "jest" in lowered):
                args.extend(["-t", filter_pattern])
            elif filter_pattern and "mocha" in lowered:
                args.extend(["--grep", filter_pattern])
            return args

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

    @staticmethod
    def _append_test_paths(cmd_args: list[str], test_paths: list[str]) -> list[str]:
        """Append targeted test files, using ``--`` only where it is required.

        ``npm test -- a.test.js`` needs the separator to reach the underlying
        script, while ``npx vitest run -- a.test.js`` does not: vitest treats
        everything after ``--`` as a positional filter anyway, and jest/mocha
        take bare paths. Adding it unconditionally broke direct invocations.
        """
        if not test_paths:
            return cmd_args
        head = Path(cmd_args[0]).stem.lower() if cmd_args else ""
        needs_separator = head in PACKAGE_MANAGERS and "--" not in cmd_args
        return [*cmd_args, *(["--"] if needs_separator else []), *test_paths]

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
        test_paths: list[str] | None = None,
    ) -> TestRunResult:
        cmd_args = self._determine_node_cmd(root_dir, custom_cmd, filter_pattern)
        # Targeted paths must reach the process that is actually spawned; the
        # previous version rebuilt the argv and then executed the raw command
        # string anyway, so incremental runs silently ran the whole suite.
        cmd_args = self._append_test_paths(cmd_args, test_paths or [])
        display_cmd = " ".join(cmd_args)

        start_time = time.time()
        exit_code, raw_output, is_timeout = execute_safe_subprocess(
            cmd_args,
            cwd=root_dir,
            timeout_seconds=timeout_seconds,
        )
        duration = round(time.time() - start_time, 2)

        framework = TestFramework.VITEST if "vitest" in display_cmd.lower() else TestFramework.JEST

        if is_timeout:
            return TestRunResult(
                ecosystem=Ecosystem.NODE,
                framework=framework,
                command=display_cmd,
                total=0,
                failed=1,
                duration_seconds=duration,
                exit_code=124,
                # Keep whatever the run managed to print: the partial output is
                # usually the only clue about *where* it hung.
                raw_output=f"Test execution timed out after {timeout_seconds} seconds.\n\n{raw_output}",
                has_executed=True,
                failures=[
                    FailureDetail(
                        test_name="Timeout",
                        error_type="TimeoutError",
                        message=f"Node test run exceeded {timeout_seconds}s limit",
                        traceback=raw_output[-1000:],
                        suggested_fix=(
                            "Raise the timeout (--timeout / timeout_seconds), or check for a watch-mode "
                            "test script, unresolved Promises, or hanging server listeners."
                        ),
                    )
                ],
            )

        passed, failed, skipped, failures = self._parse_node_output(raw_output)

        # A suite that fails to even load (import error, wrong test runner) is
        # reported by Vitest at file level only - "Test Files 1 failed | 4 passed"
        # with every *test* still green. Surfacing it as an error keeps the run
        # honest instead of showing a clean 72/0 next to exit code 1.
        suite_failed = self._parse_failed_suites(raw_output)
        errors = suite_failed if failed == 0 else 0

        total = passed + failed + skipped + errors
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
            total = 1

        return TestRunResult(
            ecosystem=Ecosystem.NODE,
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

    def _parse_failed_suites(self, output: str) -> int:
        """Number of test *files* Vitest reports as failed."""
        matches = TEST_FILES_SUMMARY_RE.findall(output)
        if not matches:
            return 0
        return _counts_from_summary(matches[-1]).get("failed", 0)

    def _parse_node_output(self, output: str) -> tuple[int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        skipped = 0
        failures: list[FailureDetail] = []

        # Jest  "Tests:       1 failed, 4 passed, 5 total"
        # Vitest "      Tests  1 failed | 71 passed | 2 skipped (74)"
        # The last summary line wins - watch/rerun output repeats it.
        summaries = TESTS_SUMMARY_RE.findall(output)
        if summaries:
            counts = _counts_from_summary(summaries[-1])
            passed = counts.get("passed", 0)
            failed = counts.get("failed", 0)
            # todo/pending are not executed either; they belong with skipped.
            skipped = counts.get("skipped", 0) + counts.get("todo", 0) + counts.get("pending", 0)

        # Mocha spec reporter: "72 passing (2s)" / "1 failing" / "2 pending"
        if passed == 0 and failed == 0 and skipped == 0:
            for number, kind in MOCHA_RE.findall(output):
                if kind == "passing":
                    passed += int(number)
                elif kind == "failing":
                    failed += int(number)
                else:
                    skipped += int(number)

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

        for name in self._failure_names(output):
            failures.append(
                FailureDetail(
                    test_name=name,
                    error_type="NodeTestFailure",
                    message="Test suite or case failed",
                    traceback="",
                    suggested_fix="Check Jest/Vitest/node:test assertion errors and mock implementations.",
                )
            )

        return passed, failed, skipped, failures

    @staticmethod
    def _failure_names(output: str) -> list[str]:
        """Collect failing suite/case names, de-duplicated and in output order.

        Vitest prints the same ``FAIL <file>`` line twice (run list and failure
        section), and decorates it with a ``[ file ]`` suffix - emitting both
        copies inflated the failure list with duplicates.
        """
        names: list[str] = []
        seen: set[str] = set()

        candidates: list[str] = []
        candidates += re.findall(r"^\s*FAIL\s+([^\n]+)", output, re.MULTILINE)
        candidates += re.findall(r"[✕×]\s+([^\n]+)", output)
        if not candidates:
            # TAP failures: "not ok N - test name"
            candidates += re.findall(r"not ok\s+\d+\s*-\s*([^\n]+)", output)

        for raw in candidates:
            name = re.sub(r"\s*\[[^\]]*\]\s*$", "", raw.strip()).strip()
            # Drop the trailing duration Vitest appends to failing cases - bare
            # (`divides 3ms`) or parenthesised (`divides (1 ms)`), with or
            # without a space before the unit.
            name = re.sub(r"\s+\(?\d+(?:\.\d+)?\s*m?s\)?$", "", name).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names
