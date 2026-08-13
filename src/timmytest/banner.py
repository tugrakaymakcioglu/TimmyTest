"""TimmyTest terminal branding, ASCII header, and styling utilities."""

import contextlib
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

ASCII_BANNER = r"""
  _____ _                            _____         _   
 |_   _(_)_ __  _ __ ___  _   _     |_   _|__  ___| |_ 
   | | | | '_ \| '_ ` _ \| | | |______| |/ _ \/ __| __|
   | | | | | | | | | | | | |_| |______| |  __/\__ \ |_ 
   |_| |_|_| |_|_| |_| |_|\__, |      |_|\___||___/\__|
                          |___/                         
"""

SUBTITLE = "Zero-AI Test Intelligence • Gap Detector • Agent Prompt Generator"


def print_banner(show_subtitle: bool = True) -> None:
    """Print the stylized TimmyTest banner."""
    banner_text = Text(ASCII_BANNER.strip("\n"), style="bold cyan")
    console.print(banner_text)
    if show_subtitle:
        console.print(f"[bold dim white]  {SUBTITLE}[/bold dim white]\n")


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
