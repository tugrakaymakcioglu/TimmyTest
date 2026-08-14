"""Base test runner abstraction and safe subprocess execution utilities."""

import os
import re
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from timmytest.detector.models import TestRunResult

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Removes terminal ANSI color and styling escape codes."""
    return ANSI_ESCAPE_RE.sub("", text)


def execute_safe_subprocess(
    cmd_args: list[str] | str,
    cwd: Path,
    timeout_seconds: int = 60,
    env: dict[str, str] | None = None,
) -> tuple[int, str, bool]:
    """
    Executes a subprocess safely without shell=True to prevent command injection,
    and ensures clean process-tree termination upon timeout.

    Returns:
        (exit_code, raw_output, is_timeout)
    """
    if isinstance(cmd_args, str):
        # Safely split command string into arguments
        try:
            args = shlex.split(cmd_args, posix=True)
        except Exception:
            args = cmd_args.split()
    else:
        args = list(cmd_args)

    if not args:
        return 1, "Empty command supplied", False

    # Resolve executable path on Windows (e.g. npm -> npm.cmd, pytest -> pytest.exe)
    exe = args[0]
    resolved_exe = shutil.which(exe, path=env.get("PATH") if env else None) or shutil.which(exe)
    if resolved_exe:
        args[0] = resolved_exe

    # Prepare environment with NO_COLOR to minimize terminal escapes
    run_env = (env or os.environ).copy()
    run_env["FORCE_COLOR"] = "0"
    run_env["NO_COLOR"] = "1"

    raw_output = ""
    is_timeout = False
    exit_code = 0

    try:
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            raw_output = (stdout or "") + ("\n" + stderr if stderr else "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            is_timeout = True
            proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=2)
                raw_output = (stdout or "") + ("\n" + stderr if stderr else "")
            except Exception:
                pass
            exit_code = 124
    except Exception as e:
        raw_output = f"Execution error: {e}"
        exit_code = 1

    return exit_code, strip_ansi(raw_output), is_timeout


class BaseRunner(ABC):
    """Abstract base runner for executing ecosystem-specific tests."""

    @abstractmethod
    def can_handle(self, root_dir: Path) -> bool:
        """Return True if this runner can execute tests in the given project root."""
        pass

    @abstractmethod
    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
    ) -> TestRunResult:
        """Run the test suite and return structured results."""
        pass
