"""TimmyTest terminal branding: pixel-art banner, splash screen and styling helpers.

The artwork is rasterised at run time from the sprites in ``timmytest.tui.pixelart``,
so it always renders at the resolution the current terminal can actually show
instead of at a fixed, pre-baked width.
"""

import contextlib
import ctypes
import os
import shutil
import sys
import time

from rich.console import Console
from rich.panel import Panel

from timmytest.tui import pixelart

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

SUBTITLE = "Zero-AI Test Intelligence • Gap Detector • Agent Prompt Generator"
AUTHOR = "Tuğra KAYMAKÇIOĞLU"

# Compact banner height in terminal rows (each row carries two pixels).
BANNER_ROWS = 14
MIN_BANNER_ROWS = 6
SPLASH_FOOTER_ROWS = 5


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size((110, 34))
    return max(40, size.columns), max(16, size.lines)


def _render_hero(columns: int, rows: int) -> list[str]:
    canvas = pixelart.compose_hero(columns, rows * 2)
    return pixelart.canvas_to_ansi(canvas)


def maximize_terminal() -> None:
    """Set the terminal window title on Windows if running in a console."""
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.kernel32.SetConsoleTitleW(
                    "⚡ TimmyTest • Zero-Token AI Test Intelligence"
                )


def print_banner(show_subtitle: bool = True) -> None:
    """Print the stylized TimmyTest banner, scaled to the current terminal."""
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    columns, rows = _terminal_size()
    banner_rows = max(MIN_BANNER_ROWS, min(BANNER_ROWS, rows - 6))
    lines = _render_hero(columns - 2, banner_rows)

    out = "\n".join(" " + line for line in lines)
    sys.stdout.write(out + "\n")
    if show_subtitle:
        sys.stdout.write(f"\033[38;2;110;118;129m  {SUBTITLE}\033[0m\n")
    sys.stdout.write(f"\033[38;2;243;226;184m  {AUTHOR}\033[0m\n\n")
    sys.stdout.flush()


def show_fullscreen_splash(animate_progress: bool = True) -> None:
    """Fill the terminal with the logo and run a white loading bar underneath it."""
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    maximize_terminal()
    columns, rows = _terminal_size()
    hero_rows = max(MIN_BANNER_ROWS, rows - SPLASH_FOOTER_ROWS - 1)
    lines = _render_hero(columns - 4, hero_rows)

    sys.stdout.write("\033[2J\033[H\033[?25l")
    sys.stdout.write("\n".join("  " + line for line in lines) + "\n")
    sys.stdout.flush()

    if animate_progress:
        steps = [
            (18, "Initializing TimmyTest core engine"),
            (37, "Loading AST test-gap detector"),
            (58, "Preparing ecosystem runners"),
            (76, "Wiring AI agent bridges"),
            (92, "Mounting MCP server layer"),
            (100, "Ready"),
        ]
        bar_width = max(20, min(columns - 16, 96))
        white = "\033[1;38;2;255;255;255m"
        track = "\033[38;2;42;48;56m"
        cream = "\033[38;2;243;226;184m"
        dim = "\033[38;2;110;118;129m"
        reset = "\033[0m"
        left = max(0, (columns - bar_width) // 2)

        sys.stdout.write("\n")
        for percent, message in steps:
            filled = int(bar_width * percent / 100)
            bar = f"{white}{'█' * filled}{track}{'─' * (bar_width - filled)}{reset}"
            status = f"{cream}{message}{reset} {dim}…{reset}"
            sys.stdout.write(f"\r{' ' * left}{bar}\n")
            sys.stdout.write(f"\r{' ' * left}{status}{' ' * 20}\033[1A")
            sys.stdout.flush()
            time.sleep(0.16 if os.environ.get("PYTEST_CURRENT_TEST") is None else 0)
        sys.stdout.write("\n\n")
        sys.stdout.write(f"{dim}{' ' * left}{AUTHOR}{reset}\n")

    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def make_header_panel(title: str, subtitle: str = "") -> Panel:
    """Create a formatted header panel."""
    content = f"[bold white]{title}[/bold white]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    return Panel(
        content,
        border_style="cyan",
        padding=(0, 2),
    )
