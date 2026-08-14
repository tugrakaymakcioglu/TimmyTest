"""Chart renderables for the dashboard: stat tiles, bars, gauges and history plots."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from timmytest.tui.state import RunSnapshot

PASS = "#3fb950"
FAIL = "#f85149"
SKIP = "#d29922"
MISS = "#a371f7"
MUTED = "#6e7681"
ACCENT = "#2f9fa8"
CREAM = "#f3e2b8"

# Eighth-block ramp gives bar charts sub-cell precision.
_EIGHTHS = " ▏▎▍▌▋▊▉█"
_VERTICAL = " ▁▂▃▄▅▆▇█"

# Big 5x3 digits, drawn with block glyphs so headline numbers read across a room.
_BIG_DIGITS = {
    "0": ["█▀█", "█ █", "▀▀▀"],
    "1": [" ▄█", "  █", "  ▀"],
    "2": ["▀▀█", "█▀▀", "▀▀▀"],
    "3": ["▀▀█", " ▀█", "▀▀▀"],
    "4": ["█ █", "▀▀█", "  ▀"],
    "5": ["█▀▀", "▀▀█", "▀▀▀"],
    "6": ["█▀▀", "█▀█", "▀▀▀"],
    "7": ["▀▀█", "  █", "  ▀"],
    "8": ["█▀█", "█▀█", "▀▀▀"],
    "9": ["█▀█", "▀▀█", "▀▀▀"],
    "%": ["█ ▄", " ▀ ", "▀ █"],
    ".": ["   ", "   ", " ▀ "],
    "-": ["   ", "▀▀▀", "   "],
}


def big_number(value: str, colour: str) -> Text:
    """Render a short string as three rows of block digits."""
    rows = ["", "", ""]
    for char in value:
        glyph = _BIG_DIGITS.get(char, ["   ", " ? ", "   "])
        for i in range(3):
            rows[i] += glyph[i] + " "
    return Text("\n".join(row.rstrip() for row in rows), style=colour)


def hbar(value: float, total: float, width: int, colour: str) -> Text:
    """A horizontal bar with eighth-cell resolution."""
    width = max(1, width)
    if total <= 0:
        return Text("─" * width, style=MUTED)
    ratio = max(0.0, min(1.0, value / total))
    exact = ratio * width
    full = int(exact)
    remainder = int((exact - full) * 8)
    bar = "█" * full
    if remainder and full < width:
        bar += _EIGHTHS[remainder]
    text = Text(bar, style=colour)
    text.append("─" * max(0, width - len(bar)), style=MUTED)
    return text


def stacked_bar(values: list[tuple[int, str]], width: int) -> Text:
    """One bar where each category owns a proportional slice."""
    total = sum(v for v, _ in values)
    text = Text()
    if total <= 0:
        return Text("─" * width, style=MUTED)
    used = 0
    for index, (value, colour) in enumerate(values):
        if value <= 0:
            continue
        cells = width - used if index == len(values) - 1 else round(width * value / total)
        cells = max(0, min(cells, width - used))
        text.append("█" * cells, style=colour)
        used += cells
    if used < width:
        text.append("─" * (width - used), style=MUTED)
    return text


def gauge(percent: float, width: int, label: str = "") -> Text:
    """Readiness gauge coloured by how healthy the score is."""
    percent = max(0.0, min(100.0, percent))
    colour = PASS if percent >= 80 else SKIP if percent >= 50 else FAIL
    text = Text()
    if label:
        text.append(f"{label}  ", style=MUTED)
    text.append_text(hbar(percent, 100, width, colour))
    text.append(f"  {percent:5.1f}%", style=f"bold {colour}")
    return text


def stat_tile(label: str, value: int | str, colour: str, hint: str = "") -> Panel:
    body = Group(
        Align.center(big_number(str(value), colour)),
        Align.center(Text(hint or " ", style=MUTED)),
    )
    return Panel(
        body,
        title=Text(label, style=f"bold {colour}"),
        border_style=colour,
        padding=(0, 1),
        expand=True,
    )


def stat_row(tiles: list[Panel]) -> Table:
    table = Table.grid(expand=True, padding=(0, 1))
    for _ in tiles:
        table.add_column(ratio=1)
    table.add_row(*tiles)
    return table


def distribution_chart(
    rows: list[tuple[str, int, str]],
    width: int = 34,
    title: str = "",
) -> RenderableType:
    """Labelled horizontal bars - the pass / fail / skip / missing breakdown."""
    total = max(1, sum(value for _, value, _ in rows))
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", style=MUTED, no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    table.add_column(justify="right", style=MUTED, no_wrap=True)
    for label, value, colour in rows:
        table.add_row(
            Text(label, style="bold"),
            hbar(value, total, width, colour),
            Text(str(value), style=f"bold {colour}"),
            Text(f"{value / total * 100:4.0f}%"),
        )
    if not title:
        return table
    return Panel(table, title=Text(title, style=f"bold {CREAM}"), border_style=MUTED, padding=(1, 2))


def history_chart(history: list[RunSnapshot], width: int = 48, height: int = 8) -> RenderableType:
    """Vertical column chart of pass / fail counts across recent runs."""
    runs = [r for r in history if r.has_data][-width:]
    if not runs:
        return Text("", style=MUTED)

    peak = max((r.passed + r.failed + r.skipped) for r in runs) or 1
    lines: list[Text] = []
    for level in range(height, 0, -1):
        line = Text()
        for run in runs:
            total = run.passed + run.failed + run.skipped
            filled = total / peak * height
            if filled >= level:
                colour = FAIL if run.failed else PASS
                line.append("█", style=colour)
            elif filled >= level - 1:
                fraction = filled - (level - 1)
                colour = FAIL if run.failed else PASS
                line.append(_VERTICAL[max(1, int(fraction * 8))], style=colour)
            else:
                line.append(" ")
            line.append(" ")
        lines.append(line)

    axis = Text("─" * (len(runs) * 2), style=MUTED)
    scale = Text(f"peak {peak}", style=MUTED)
    return Group(*lines, axis, scale)


def sparkline(values: list[float], colour: str = ACCENT) -> Text:
    if not values:
        return Text("")
    peak = max(values) or 1
    text = Text()
    for value in values:
        index = max(0, min(8, int(value / peak * 8)))
        text.append(_VERTICAL[index], style=colour)
    return text


def kv_table(rows: list[tuple[str, RenderableType]], key_style: str = MUTED) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style=key_style, no_wrap=True)
    table.add_column(overflow="fold")
    for key, value in rows:
        table.add_row(key, value)
    return table


def section(title: str, body: RenderableType, border: str = MUTED) -> Panel:
    return Panel(body, title=Text(title, style=f"bold {CREAM}"), border_style=border, padding=(1, 2))
