"""Cross-platform clipboard utility."""

import platform
import shutil
import subprocess


def copy_to_clipboard(text: str) -> bool:
    """
    Copies text to the system clipboard across Windows, macOS, and Linux
    without raising exceptions. Returns True on success, False on failure.
    """
    os_name = platform.system()

    try:
        if os_name == "Windows":
            # Use clip.exe on Windows
            proc = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
            proc.communicate(text.encode("utf-16le"))
            return proc.returncode == 0

        elif os_name == "Darwin":
            # Use pbcopy on macOS
            proc = subprocess.Popen("pbcopy", stdin=subprocess.PIPE)
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
