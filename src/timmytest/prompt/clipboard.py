"""Cross-platform clipboard utility with safe execution."""

import platform
import shutil
import subprocess

from timmytest import flags


def copy_to_clipboard(text: str) -> bool:
    """
    Copies text to the system clipboard across Windows, macOS, and Linux
    without raising exceptions and without using shell=True.
    Returns True on success, False on failure.

    Returns False without touching the clipboard when the ``core.clipboard``
    switch is off - some teams forbid tools writing to a shared clipboard.
    """
    if not flags.is_enabled("core.clipboard"):
        return False

    os_name = platform.system()

    try:
        if os_name == "Windows":
            # Use clip.exe without shell=True
            clip_exe = shutil.which("clip.exe") or "clip"
            proc = subprocess.Popen([clip_exe], stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-16le"))
            return proc.returncode == 0

        elif os_name == "Darwin":
            # Use pbcopy on macOS
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            return proc.returncode == 0

        else:
            # Linux: try wl-copy, then xclip, then xsel
            if shutil.which("wl-copy"):
                proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return proc.returncode == 0
            elif shutil.which("xclip"):
                proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return proc.returncode == 0
            elif shutil.which("xsel"):
                proc = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return proc.returncode == 0

        return False
    except Exception:
        return False
