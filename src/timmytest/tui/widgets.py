"""Custom Textual widgets: pixel-art canvases, the TT badge and the loading bar."""

from __future__ import annotations

from collections.abc import Callable

from rich.segment import Segment
from rich.text import Text
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static

from timmytest.tui import pixelart
from timmytest.tui.pixelart import Grid

CanvasBuilder = Callable[[int, int], Grid]


class PixelArt(Widget):
    """Rasterises a pixel canvas to fill whatever space the widget is given.

    The canvas is rebuilt on every resize, so the artwork is always drawn at the
    highest resolution the current terminal can show rather than at a fixed,
    baked-in size.
    """

    DEFAULT_CSS = """
    PixelArt {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self, builder: CanvasBuilder, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._builder = builder
        self._rows: list[list[Segment]] = []
        self._raster_size: tuple[int, int] | None = None

    def set_builder(self, builder: CanvasBuilder) -> None:
        self._builder = builder
        self._raster_size = None
        self.refresh()

    def _rasterise(self) -> None:
        width, height = self.size.width, self.size.height
        if (width, height) == self._raster_size:
            return
        self._raster_size = (width, height)
        if width < 2 or height < 1:
            self._rows = []
            return
        canvas = self._builder(width, height * 2)
        self._rows = pixelart.canvas_to_segments(canvas)

    def render_line(self, y: int) -> Strip:
        self._rasterise()
        if 0 <= y < len(self._rows):
            return Strip(self._rows[y], self.size.width)
        return Strip.blank(self.size.width)

    def on_resize(self) -> None:
        self._raster_size = None
        self.refresh()


class Badge(Widget):
    """The hand-drawn pixel-art 'TT' mark used in the dashboard header."""

    DEFAULT_CSS = f"""
    Badge {{
        width: {pixelart.BADGE_WIDTH};
        height: {pixelart.BADGE_HEIGHT};
    }}
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._rows = pixelart.badge_segments()

    def render_line(self, y: int) -> Strip:
        if 0 <= y < len(self._rows):
            return Strip(self._rows[y], pixelart.BADGE_WIDTH)
        return Strip.blank(self.size.width)


class LoadingBar(Static):
    """A wide white progress bar drawn with eighth-cell precision."""

    DEFAULT_CSS = """
    LoadingBar {
        width: 1fr;
        height: 1;
        color: $text;
    }
    """

    EIGHTHS = " ▏▎▍▌▋▊▉█"

    def __init__(self, colour: str = "#ffffff", track: str = "#2a3038", **kwargs: object) -> None:
        super().__init__("", **kwargs)  # type: ignore[arg-type]
        self._percent = 0.0
        self._colour = colour
        self._track = track

    @property
    def percent(self) -> float:
        return self._percent

    def set_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.refresh()

    def render(self) -> Text:
        width = max(1, self.size.width)
        exact = self._percent / 100 * width
        full = int(exact)
        remainder = int((exact - full) * 8)
        text = Text()
        text.append("█" * full, style=self._colour)
        if remainder and full < width:
            text.append(self.EIGHTHS[remainder], style=self._colour)
            full += 1
        text.append("─" * max(0, width - full), style=self._track)
        return text
