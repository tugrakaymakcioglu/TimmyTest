"""Python test runner supporting pytest and unittest with rich traceback parsing."""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from timmytest.detector.models import Ecosystem, FailureDetail, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner


class PythonRunner(BaseRunner):
    """Executes Python tests using pytest or unittest."""

    def can_handle(self, root_dir: Path) -> bool:
        return (
            (root_dir / "pyproject.toml").exists()
            or (root_dir / "setup.py").exists()
            or (root_dir / "pytest.ini").exists()
            or any(root_dir.glob("tests/**/*.py"))
            or any(root_dir.glob("test_*.py"))
        )

    def _find_python_executable(self, root_dir: Path) -> str:
        """Find the best python executable (local .venv or current sys.executable)."""
        venv_scripts = root_dir / ".venv" / "Scripts" / "python.exe"
        venv_bin = root_dir / ".venv" / "bin" / "python"

        if venv_scripts.exists():
            return str(venv_scripts)
        if venv_bin.exists():
            return str(venv_bin)
        return sys.executable

    def _find_pytest_executable(self, root_dir: Path) -> str:
        """Find pytest inside local .venv, system PATH, or fallback to current python -m pytest."""
        import shutil

        venv_pytest_win = root_dir / ".venv" / "Scripts" / "pytest.exe"
        venv_pytest_nix = root_dir / ".venv" / "bin" / "pytest"

        if venv_pytest_win.exists():
            return f'"{venv_pytest_win}"'
        if venv_pytest_nix.exists():
            return f'"{venv_pytest_nix}"'
        if shutil.which("pytest"):
            return "pytest"
        return f'"{sys.executable}" -m pytest'

    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
    ) -> TestRunResult:
        pytest_exe = self._find_pytest_executable(root_dir)

        # Decide command
        if custom_cmd:
            cmd = custom_cmd
        else:
            # Try pytest first with -v --tb=short
            cmd_args = [pytest_exe, "-v", "--tb=short"]
            if filter_pattern:
                cmd_args.extend(["-k", filter_pattern])
            cmd = " ".join(cmd_args)

        env = os.environ.copy()
        # Add project root and src to PYTHONPATH
        src_path = str(root_dir / "src")
        root_str = str(root_dir)
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{root_str}{os.pathsep}{src_path}{os.pathsep}{current_pythonpath}".strip(
            os.pathsep
        )

        start_time = time.time()
        exit_code = 0
        raw_output = ""

        try:
            # Run test process
            proc = subprocess.run(
                cmd,
                cwd=str(root_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            raw_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            return TestRunResult(
                ecosystem=Ecosystem.PYTHON,
                framework=TestFramework.PYTEST,
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
                        message=f"Test run exceeded {timeout_seconds}s limit",
                        suggested_fix="Check for infinite loops or increase timeout via --timeout",
                    )
                ],
            )
        except Exception as e:
            raw_output = f"Execution error: {e}"
            exit_code = 1

        duration = round(time.time() - start_time, 2)

        # Parse pytest output
        passed, failed, skipped, errors, failures = self._parse_pytest_output(raw_output)

        # Fallback to unittest parsing if pytest failed to find tests and exit code indicates failure
        if passed == 0 and failed == 0 and errors == 0 and "Ran " in raw_output:
            passed, failed, skipped, errors, failures = self._parse_unittest_output(raw_output)

        total = passed + failed + skipped + errors
        if total == 0 and exit_code != 0:
            # Collect configuration or syntax failure
            failed = 1
            failures.append(
                FailureDetail(
                    test_name="Collection/Setup Error",
                    error_type="SetupError",
                    message="Failed to collect or execute tests. See raw output.",
                    traceback=raw_output[:1000],
                    suggested_fix="Ensure test dependencies are installed and test syntax is valid.",
                )
            )

        return TestRunResult(
            ecosystem=Ecosystem.PYTHON,
            framework=TestFramework.PYTEST,
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

    def _parse_pytest_output(self, output: str) -> tuple[int, int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        failures: list[FailureDetail] = []

        # Count from status lines e.g. tests/test_a.py::test_b PASSED
        for line in output.splitlines():
            if re.search(r"::\S+\s+PASSED", line):
                passed += 1
            elif re.search(r"::\S+\s+FAILED", line):
                failed += 1
            elif re.search(r"::\S+\s+SKIPPED", line):
                skipped += 1
            elif re.search(r"::\S+\s+ERROR", line):
                errors += 1

        # Summary line fallback e.g. "= 2 failed, 8 passed, 1 skipped in 0.12s ="
        summary_match = re.search(r"=+\s*(.+?)\s*in\s+[\d\.]+s\s*=+", output)
        if summary_match:
            summary_text = summary_match.group(1)
            p_m = re.search(r"(\d+)\s+passed", summary_text)
            f_m = re.search(r"(\d+)\s+failed", summary_text)
            s_m = re.search(r"(\d+)\s+skipped", summary_text)
            e_m = re.search(r"(\d+)\s+error", summary_text)

            if p_m:
                passed = int(p_m.group(1))
            if f_m:
                failed = int(f_m.group(1))
            if s_m:
                skipped = int(s_m.group(1))
            if e_m:
                errors = int(e_m.group(1))

        # Parse detailed failures block
        failures_section = re.search(
            r"=+\s*FAILURES\s*=+(.*?)(?:=+\s*short test summary|=+$)", output, re.DOTALL
        )
        if failures_section:
            fail_blocks = re.split(r"_{3,}\s+(.*?)\s+_{3,}", failures_section.group(1))
            # Split produces [leading_text, test_name_1, body_1, test_name_2, body_2, ...]
            i = 1
            while i < len(fail_blocks) - 1:
                test_name = fail_blocks[i].strip()
                body = fail_blocks[i + 1].strip()
                i += 2

                file_path = ""
                line_num = None
                err_type = "AssertionError"
                msg = ""

                # Look for file and line
                file_match = re.search(r"([a-zA-Z0-9_\-\./\\]+\.py):(\d+):", body)
                if file_match:
                    file_path = file_match.group(1)
                    line_num = int(file_match.group(2))

                # Look for error line e.g. E   AssertionError: assert 1 == 2
                err_match = re.search(
                    r"E\s+([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception|[A-Za-z0-9_]+):\s*(.+)", body
                )
                if err_match:
                    err_type = err_match.group(1)
                    msg = err_match.group(2).strip()
                else:
                    # Generic E line
                    e_lines = [
                        line_item[2:].strip() for line_item in body.splitlines() if line_item.startswith("E ")
                    ]
                    if e_lines:
                        msg = " | ".join(e_lines[:2])

                failures.append(
                    FailureDetail(
                        test_name=test_name,
                        file_path=file_path,
                        line_number=line_num,
                        error_type=err_type,
                        message=msg or "Test failed",
                        traceback="\n".join(body.splitlines()[-15:]),
                    )
                )

        return passed, failed, skipped, errors, failures

    def _parse_unittest_output(self, output: str) -> tuple[int, int, int, int, list[FailureDetail]]:
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        failures: list[FailureDetail] = []

        ran_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
        total_ran = int(ran_match.group(1)) if ran_match else 0

        fail_match = re.search(r"failures=(\d+)", output)
        err_match = re.search(r"errors=(\d+)", output)
        skip_match = re.search(r"skipped=(\d+)", output)

        if fail_match:
            failed = int(fail_match.group(1))
        if err_match:
            errors = int(err_match.group(1))
        if skip_match:
            skipped = int(skip_match.group(1))

        passed = max(0, total_ran - failed - errors - skipped)

        # Parse FAIL / ERROR blocks
        blocks = re.findall(
            r"={5,}\n(?:FAIL|ERROR):\s+([^\n]+)\n-{5,}\n(.*?)(?=\n={5,}|\n-{5,}|\Z)",
            output,
            re.DOTALL,
        )
        for t_name, t_body in blocks:
            failures.append(
                FailureDetail(
                    test_name=t_name.strip(),
                    error_type="UnittestError",
                    message=t_body.strip().splitlines()[-1] if t_body.strip() else "Test failed",
                    traceback="\n".join(t_body.strip().splitlines()[-10:]),
                )
            )

        return passed, failed, skipped, errors, failures
