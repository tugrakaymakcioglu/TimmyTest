"""Terminal pixel-art engine.

Sprites are stored as compact ``TTPX1`` blobs (see ``tools/build_art.py``) and are
rasterised on demand for whatever size the terminal happens to be. Every terminal
cell carries two vertically stacked pixels via the upper-half-block glyph, so a
40-row area really is an 80 pixel tall canvas; because those pixels are square in
every common terminal font the aspect ratio needs no fudge factor.

Only ``base64``/``zlib``/``struct`` are needed at runtime - Pillow is a build-time
dependency exclusively.
"""

from __future__ import annotations

import base64
import struct
import zlib
from collections.abc import Callable

from rich.color import Color
from rich.segment import Segment
from rich.style import Style

from timmytest.tui import art_data

RGB = tuple[int, int, int]
Pixel = RGB | None
Grid = list[list[Pixel]]

UPPER_HALF = "▀"
LOWER_HALF = "▄"
FULL_BLOCK = "█"


class Sprite:
    """A decoded raster with a cache of every size it has been scaled to."""

    __slots__ = ("width", "height", "_palette", "_indices", "_cache")

    def __init__(self, width: int, height: int, palette: list[Pixel], indices: bytes) -> None:
        self.width = width
        self.height = height
        self._palette = palette
        self._indices = indices
        self._cache: dict[tuple[int, int], Grid] = {}

    @classmethod
    def from_b64(cls, blob: str) -> Sprite:
        raw = base64.b64decode(blob)
        magic, width, height, n_colors = struct.unpack_from("<5sHHB", raw, 0)
        if magic != b"TTPX1":
            raise ValueError(f"unsupported sprite container: {magic!r}")
        offset = struct.calcsize("<5sHHB")
        palette_bytes = raw[offset : offset + (n_colors - 1) * 3]
        offset += (n_colors - 1) * 3
        indices = zlib.decompress(raw[offset:])

        palette: list[Pixel] = [None]
        palette.extend(
            (palette_bytes[i], palette_bytes[i + 1], palette_bytes[i + 2])
            for i in range(0, len(palette_bytes), 3)
        )
        return cls(width, height, palette, indices)

    @property
    def aspect(self) -> float:
        """Width divided by height, in square pixels."""
        return self.width / self.height

    def scaled(self, out_w: int, out_h: int) -> Grid:
        """Resample to ``out_w`` x ``out_h`` square pixels (box filter, alpha aware)."""
        out_w = max(1, out_w)
        out_h = max(1, out_h)
        key = (out_w, out_h)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        src_w, src_h, palette, indices = self.width, self.height, self._palette, self._indices
        x_ratio = src_w / out_w
        y_ratio = src_h / out_h

        # Precompute the source span of every output column once.
        x_spans = []
        for x in range(out_w):
            x0 = int(x * x_ratio)
            x1 = max(x0 + 1, int((x + 1) * x_ratio))
            x_spans.append((x0, min(x1, src_w)))

        grid: Grid = []
        for y in range(out_h):
            y0 = int(y * y_ratio)
            y1 = min(max(y0 + 1, int((y + 1) * y_ratio)), src_h)
            row: list[Pixel] = []
            for x0, x1 in x_spans:
                r = g = b = 0
                solid = 0
                total = 0
                for sy in range(y0, y1):
                    base = sy * src_w
                    for si in range(base + x0, base + x1):
                        total += 1
                        colour = palette[indices[si]]
                        if colour is not None:
                            solid += 1
                            r += colour[0]
                            g += colour[1]
                            b += colour[2]
                # A pixel survives when at least half of its footprint is opaque,
                # which keeps outlines crisp instead of smearing them into the void.
                if solid * 2 >= total and solid:
                    row.append((r // solid, g // solid, b // solid))
                else:
                    row.append(None)
            grid.append(row)

        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[key] = grid
        return grid


def _lazy(blob_getter: Callable[[], str]) -> Callable[[], Sprite]:
    cell: list[Sprite | None] = [None]

    def get() -> Sprite:
        sprite = cell[0]
        if sprite is None:
            sprite = cell[0] = Sprite.from_b64(blob_getter())
        return sprite

    return get


timmy_sprite = _lazy(lambda: art_data.TIMMY_B64)
wordmark_sprite = _lazy(lambda: art_data.WORDMARK_B64)
logo_sprite = _lazy(lambda: art_data.LOGO_TT_B64)


# --------------------------------------------------------------------------- #
# Canvas helpers
# --------------------------------------------------------------------------- #


def new_canvas(width: int, height: int) -> Grid:
    return [[None for _ in range(width)] for _ in range(height)]


def blit(canvas: Grid, grid: Grid, left: int, top: int) -> None:
    """Paste ``grid`` onto ``canvas``, skipping transparent pixels."""
    canvas_h = len(canvas)
    canvas_w = len(canvas[0]) if canvas_h else 0
    for y, row in enumerate(grid):
        cy = top + y
        if cy < 0 or cy >= canvas_h:
            continue
        target = canvas[cy]
        for x, pixel in enumerate(row):
            cx = left + x
            if pixel is not None and 0 <= cx < canvas_w:
                target[cx] = pixel


def compose_hero(width: int, height: int, gap_ratio: float = 0.06) -> Grid:
    """Lay Timmy and the wordmark side by side, as large as ``width`` x ``height`` allows.

    The wordmark keeps the 0.78 height ratio it has in the source artwork, and the
    pair is scaled until it touches either the width or the height of the canvas -
    so the splash always uses every pixel the terminal is willing to give.
    """
    canvas = new_canvas(width, height)
    if width < 12 or height < 8:
        return canvas

    timmy = timmy_sprite()
    wordmark = wordmark_sprite()

    wordmark_scale = 0.78
    gap = max(2, int(width * gap_ratio))

    # Width of the composition when Timmy is exactly `h` pixels tall.
    def total_width(h: float) -> float:
        return h * timmy.aspect + gap + (h * wordmark_scale) * wordmark.aspect

    timmy_h = float(height)
    if total_width(timmy_h) > width:
        timmy_h = (width - gap) / (timmy.aspect + wordmark_scale * wordmark.aspect)

    timmy_h_i = max(4, int(timmy_h))
    timmy_w_i = max(2, round(timmy_h_i * timmy.aspect))
    word_h_i = max(3, int(timmy_h_i * wordmark_scale))
    word_w_i = max(2, round(word_h_i * wordmark.aspect))

    content_w = timmy_w_i + gap + word_w_i
    left = max(0, (width - content_w) // 2)
    top = max(0, (height - timmy_h_i) // 2)

    blit(canvas, timmy.scaled(timmy_w_i, timmy_h_i), left, top)
    # The wordmark is optically centred against Timmy's torso, not his boots.
    word_top = top + int((timmy_h_i - word_h_i) * 0.44)
    blit(canvas, wordmark.scaled(word_w_i, word_h_i), left + timmy_w_i + gap, word_top)
    return canvas


def compose_sprite(sprite: Sprite, width: int, height: int) -> Grid:
    """Fit a single sprite inside the canvas, centred."""
    canvas = new_canvas(width, height)
    if width < 2 or height < 2:
        return canvas
    scale = min(width / (height * sprite.aspect), 1.0)
    h = max(2, int(height * scale))
    w = max(2, round(h * sprite.aspect))
    blit(canvas, sprite.scaled(w, h), (width - w) // 2, (height - h) // 2)
    return canvas


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _style(top: Pixel, bottom: Pixel) -> tuple[str, Style]:
    """Pick the glyph and colours that reproduce a two pixel tall cell exactly."""
    if top is None and bottom is None:
        return " ", Style.null()
    if bottom is None:
        return UPPER_HALF, Style(color=Color.from_rgb(*top))  # type: ignore[misc]
    if top is None:
        return LOWER_HALF, Style(color=Color.from_rgb(*bottom))
    if top == bottom:
        return FULL_BLOCK, Style(color=Color.from_rgb(*top))
    return UPPER_HALF, Style(color=Color.from_rgb(*top), bgcolor=Color.from_rgb(*bottom))


def canvas_to_segments(canvas: Grid) -> list[list[Segment]]:
    """Convert a pixel canvas into one list of segments per terminal row."""
    rows: list[list[Segment]] = []
    height = len(canvas)
    width = len(canvas[0]) if height else 0
    for y in range(0, height, 2):
        top_row = canvas[y]
        bottom_row = canvas[y + 1] if y + 1 < height else [None] * width
        segments: list[Segment] = []
        run_text: list[str] = []
        run_style: Style | None = None
        for x in range(width):
            glyph, style = _style(top_row[x], bottom_row[x])
            if run_style is not None and style == run_style:
                run_text.append(glyph)
            else:
                if run_style is not None:
                    segments.append(Segment("".join(run_text), run_style))
                run_text = [glyph]
                run_style = style
        if run_style is not None:
            segments.append(Segment("".join(run_text), run_style))
        rows.append(segments)
    return rows


def canvas_to_ansi(canvas: Grid) -> list[str]:
    """Render a canvas to raw ANSI strings (used outside the Textual app)."""
    lines: list[str] = []
    for segments in canvas_to_segments(canvas):
        parts: list[str] = []
        for segment in segments:
            style = segment.style
            codes: list[str] = []
            if style is not None and style.color is not None:
                r, g, b = style.color.get_truecolor()
                codes.append(f"38;2;{r};{g};{b}")
            if style is not None and style.bgcolor is not None:
                r, g, b = style.bgcolor.get_truecolor()
                codes.append(f"48;2;{r};{g};{b}")
            if codes:
                parts.append(f"\033[{';'.join(codes)}m{segment.text}\033[0m")
            else:
                parts.append(segment.text)
        lines.append("".join(parts))
    return lines


# --------------------------------------------------------------------------- #
# Hand drawn "TT" badge for the dashboard header
# --------------------------------------------------------------------------- #

# Downscaling the photographic logo below ~10 px tall turns it to mush, so the
# header badge is drawn by hand at exactly the size it is displayed.
_TT_BADGE = [
    "ooooooooo.ooooooooo",
    "oRRRRRRRo.oTTTTTTTo",
    "oooRRRooo.oooTTTooo",
    "..oRRRo.....oTTTo..",
    "..oRRRo.....oTTTo..",
    "..oRRRo.....oTTTo..",
    "..oRRRo.....oTTTo..",
    "..ooooo.....ooooo..",
]
_BADGE_COLOURS: dict[str, Pixel] = {
    "R": (196, 62, 43),
    "T": (33, 124, 133),
    "o": (243, 226, 184),
    ".": None,
}


def badge_segments() -> list[list[Segment]]:
    """Segments for the 15x3 cell pixel-art 'TT' badge."""
    canvas: Grid = [[_BADGE_COLOURS[ch] for ch in row] for row in _TT_BADGE]
    return canvas_to_segments(canvas)


BADGE_WIDTH = len(_TT_BADGE[0])
BADGE_HEIGHT = len(_TT_BADGE) // 2
