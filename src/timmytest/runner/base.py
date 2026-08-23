"""Base test runner abstraction and safe subprocess execution utilities."""

import contextlib
import os
import re
import shlex
import shutil
import signal
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from timmytest.detector.models import TestRunResult

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Removes terminal ANSI color and styling escape codes."""
    return ANSI_ESCAPE_RE.sub("", text)


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort termination of a process and all of its children.

    ``proc.kill()`` alone only signals the direct child, leaving grandchildren
    orphaned (e.g. a test that spawns a server). On Windows we use
    ``taskkill /T`` to walk the tree; on POSIX we run the child in its own
    process group and ``killpg`` it.
    """
    with contextlib.suppress(Exception):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            killpg = getattr(os, "killpg", None)
            getpgid = getattr(os, "getpgid", None)
            if killpg is not None and getpgid is not None:
                killpg(getpgid(proc.pid), getattr(signal, "SIGKILL", signal.SIGTERM))
    with contextlib.suppress(Exception):
        proc.kill()


def split_command(command: str) -> list[str]:
    """Split a command string into argv, correctly on both platforms.

    ``shlex.split(posix=True)`` treats a backslash as an escape character, so on
    Windows it silently eats path separators - ``C:\\tools\\pytest.exe -ra`` comes
    out as ``C:toolspytest.exe``. Windows therefore gets the non-POSIX split
    (which preserves backslashes) with the surrounding quotes stripped off each
    token, since those quotes are shell syntax and must not reach the program.
    """
    try:
        if os.name == "nt":
            parts = shlex.split(command, posix=False)
            return [
                part[1:-1] if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'" else part
                for part in parts
            ]
        return shlex.split(command, posix=True)
    except ValueError:
        # Unbalanced quotes: a naive split beats refusing to run at all.
        return command.split()


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
    args = split_command(cmd_args) if isinstance(cmd_args, str) else list(cmd_args)

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
            # No inherited terminal: a test runner that sees a TTY on stdin
            # starts in watch mode and never exits (the run then dies on the
            # timeout and reports a bogus "1 failed"), and an interactive child
            # would otherwise steal keystrokes from the TUI.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
            start_new_session=(os.name != "nt"),
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            raw_output = (stdout or "") + ("\n" + stderr if stderr else "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            is_timeout = True
            _terminate_process_tree(proc)
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
        test_paths: list[str] | None = None,
    ) -> TestRunResult:
        """Run the test suite and return structured results."""
        pass
