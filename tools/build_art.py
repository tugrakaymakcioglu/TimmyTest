"""Build-time tool: convert the Timmy source artwork into embedded terminal render data.

Usage (requires Pillow, install with: uv pip install pillow):

    python tools/build_art.py                 # regenerate src/timmytest/tui/art_data.py
    python tools/build_art.py --preview DIR   # also dump PNG previews of every sprite

The generated module contains one compact, self-contained blob per sprite:

    b"TTPX1" | uint16 width | uint16 height | uint8 n_colors
    | palette RGB bytes ((n_colors - 1) * 3)
    | zlib(index bytes, w * h)

Palette index 0 always means "transparent"; real colours start at index 1. The
runtime decoder in ``timmytest.tui.pixelart`` only needs ``zlib``/``base64`` from
the standard library, so Pillow stays a build-only dependency.
"""

from __future__ import annotations

import argparse
import base64
import struct
import sys
import textwrap
import zlib
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - build tool only
    sys.exit("Pillow is required: uv pip install pillow")

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_IMAGE = REPO_ROOT / "assets" / "timmy_source.png"
TARGET_MODULE = REPO_ROOT / "src" / "timmytest" / "tui" / "art_data.py"

BG_SENTINEL = (255, 0, 255)
BG_THRESHOLD = 42
# The studio background is a bright, almost neutral cream (252,245,235) whereas
# every cream *inside* the artwork is far more yellow, so a low red-blue spread
# separates the two reliably.
BG_MIN_RGB = (232, 226, 212)
BG_MAX_WARMTH = 30
# Enclosed background pockets (between the legs, inside the "y" of Timmy) are
# thousands of pixels; specular highlights in the eyes are a handful.
BG_POCKET_MIN_AREA = 90

# Rasters are stored at roughly 2x the largest size a terminal can realistically
# show, which leaves headroom for supersampled downscaling without bloating the
# wheel.
TIMMY_MAX = (240, 420)
WORDMARK_MAX = (380, 320)
LOGO_MAX = (120, 96)


def key_out_background(image: Image.Image) -> Image.Image:
    """Flood fill the flat studio background from the borders and turn it into alpha."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    flooded = rgb.copy()
    seeds = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]
    for seed in seeds:
        ImageDraw.floodfill(flooded, seed, BG_SENTINEL, thresh=BG_THRESHOLD)

    alpha = Image.new("L", (w, h), 255)
    alpha_px = alpha.load()
    flood_px = flooded.load()
    for y in range(h):
        for x in range(w):
            if flood_px[x, y] == BG_SENTINEL:
                alpha_px[x, y] = 0

    _clear_background_pockets(rgb, alpha)

    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def _clear_background_pockets(rgb: Image.Image, alpha: Image.Image) -> None:
    """Erase enclosed background areas the border flood fill could never reach."""
    w, h = rgb.size
    rgb_px = rgb.load()
    alpha_px = alpha.load()

    def looks_like_background(x: int, y: int) -> bool:
        r, g, b = rgb_px[x, y]
        return r >= BG_MIN_RGB[0] and g >= BG_MIN_RGB[1] and b >= BG_MIN_RGB[2] and (r - b) <= BG_MAX_WARMTH

    seen = bytearray(w * h)
    cleared = 0
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0 * w + x0] or alpha_px[x0, y0] == 0 or not looks_like_background(x0, y0):
                continue
            stack = [(x0, y0)]
            seen[y0 * w + x0] = 1
            pocket = []
            while stack:
                x, y = stack.pop()
                pocket.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    inside = 0 <= nx < w and 0 <= ny < h
                    if (
                        inside
                        and not seen[ny * w + nx]
                        and alpha_px[nx, ny]
                        and looks_like_background(nx, ny)
                    ):
                        seen[ny * w + nx] = 1
                        stack.append((nx, ny))
            if len(pocket) >= BG_POCKET_MIN_AREA:
                cleared += len(pocket)
                for x, y in pocket:
                    alpha_px[x, y] = 0
    print(f"cleared {cleared} enclosed background pixels")


def find_split_column(rgba: Image.Image, lo_frac: float = 0.40, hi_frac: float = 0.50) -> int:
    """Find the emptiest column between the character and the wordmark."""
    w, h = rgba.size
    alpha = rgba.getchannel("A").load()
    lo, hi = int(w * lo_frac), int(w * hi_frac)
    best_x, best_score = lo, None
    for x in range(lo, hi):
        score = sum(1 for y in range(0, h, 2) if alpha[x, y] > 8)
        if best_score is None or score < best_score:
            best_x, best_score = x, score
    return best_x


def fit(size: tuple[int, int], max_size: tuple[int, int]) -> tuple[int, int]:
    """Scale ``size`` down so it fits inside ``max_size``, preserving aspect ratio."""
    w, h = size
    mw, mh = max_size
    scale = min(mw / w, mh / h, 1.0)
    return max(1, round(w * scale)), max(1, round(h * scale))


def resample(rgba: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    """High quality downscale that will not bleed the transparent halo into edges."""
    target = fit(rgba.size, max_size)
    premultiplied = rgba.convert("RGBa")
    return premultiplied.resize(target, Image.Resampling.LANCZOS).convert("RGBA")


def encode_sprite(rgba: Image.Image, colors: int = 200, alpha_cutoff: int = 110) -> bytes:
    """Quantize a sprite and pack it into the TTPX1 container format."""
    w, h = rgba.size
    mask = rgba.getchannel("A").point(lambda a: 255 if a >= alpha_cutoff else 0)
    flat = Image.new("RGB", (w, h), (0, 0, 0))
    flat.paste(rgba.convert("RGB"), (0, 0), mask)

    quantized = flat.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = quantized.getpalette()[: colors * 3]
    indices = bytearray(quantized.tobytes())
    mask_px = mask.tobytes()

    for i, opaque in enumerate(mask_px):
        indices[i] = 0 if not opaque else indices[i] + 1

    header = struct.pack("<5sHHB", b"TTPX1", w, h, colors + 1)
    return header + bytes(palette) + zlib.compress(bytes(indices), 9)


def crop_content(rgba: Image.Image) -> Image.Image:
    box = rgba.getbbox()
    return rgba.crop(box) if box else rgba


def build_logo(wordmark: Image.Image) -> Image.Image:
    """Compose the square 'TT' badge out of the two real capital T glyphs."""
    w, h = wordmark.size
    # Fractions measured against the wordmark bounding box: the red "T" of
    # "Timmy" sits top-left, the teal "T" of "Test" directly underneath it.
    red_t = crop_content(wordmark.crop((int(w * 0.005), int(h * 0.00), int(w * 0.21), int(h * 0.46))))
    teal_t = crop_content(wordmark.crop((int(w * 0.02), int(h * 0.47), int(w * 0.23), int(h * 1.0))))

    height = min(red_t.height, teal_t.height)
    red_t = red_t.resize(
        (max(1, round(red_t.width * height / red_t.height)), height), Image.Resampling.LANCZOS
    )
    teal_t = teal_t.resize(
        (max(1, round(teal_t.width * height / teal_t.height)), height), Image.Resampling.LANCZOS
    )

    gap = max(1, height // 12)
    canvas = Image.new("RGBA", (red_t.width + teal_t.width + gap, height), (0, 0, 0, 0))
    canvas.alpha_composite(red_t, (0, 0))
    canvas.alpha_composite(teal_t, (red_t.width + gap, 0))
    return canvas


def as_literal(name: str, blob: bytes) -> str:
    encoded = base64.b64encode(blob).decode("ascii")
    wrapped = textwrap.wrap(encoded, 96)
    body = "\n".join(f'    "{chunk}"' for chunk in wrapped)
    return f"{name} = (\n{body}\n)\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate embedded pixel-art data")
    parser.add_argument("--source", type=Path, default=SOURCE_IMAGE)
    parser.add_argument("--out", type=Path, default=TARGET_MODULE)
    parser.add_argument("--preview", type=Path, default=None, help="Directory to dump PNG previews into")
    args = parser.parse_args()

    original = Image.open(args.source)
    keyed = key_out_background(original)
    keyed = crop_content(keyed)

    split_x = find_split_column(keyed)
    character = crop_content(keyed.crop((0, 0, split_x, keyed.height)))
    wordmark = crop_content(keyed.crop((split_x, 0, keyed.width, keyed.height)))
    logo = build_logo(wordmark)

    sprites = {
        "TIMMY": resample(character, TIMMY_MAX),
        "WORDMARK": resample(wordmark, WORDMARK_MAX),
        "LOGO_TT": resample(logo, LOGO_MAX),
    }

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        for name, sprite in sprites.items():
            sprite.save(args.preview / f"{name.lower()}.png")
        keyed.save(args.preview / "keyed.png")

    blobs = {name: encode_sprite(sprite) for name, sprite in sprites.items()}

    lines = [
        '"""Embedded pixel-art rasters for the TimmyTest terminal UI.',
        "",
        "Generated by ``tools/build_art.py`` from ``assets/timmy_source.png``.",
        "Do not edit by hand - rerun the tool instead.",
        '"""',
        "",
    ]
    for name, blob in blobs.items():
        sprite = sprites[name]
        lines.append(f"# {name}: {sprite.width}x{sprite.height} px, {len(blob) / 1024:.1f} KiB packed")
        lines.append(as_literal(f"{name}_B64", blob))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")

    print(f"split column: x={split_x}")
    for name, sprite in sprites.items():
        print(f"{name:9s} {sprite.width:4d}x{sprite.height:<4d} -> {len(blobs[name]) / 1024:6.1f} KiB")
    print(f"written: {args.out}")


if __name__ == "__main__":
    main()
