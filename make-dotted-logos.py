# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10", "numpy>=1.24", "pymupdf>=1.24"]
# ///
"""Render the faint pane logos as a dot grid (like the Devin CLI banner logo).

The trademarked marks (Claude, Devin, Ghostty) aren't stored in this repo: their official
images are downloaded into OUT/sources/ on first run. opencode/codex masks are drawn here.
CLI logos get an opaque backing in the theme background so they cover the Ghostty ghost,
which every pane shows as its background-image while it's just a shell.

Run: uv run make-dotted-logos.py [--bg '#1e1e2e'] [--fg '#cdd6f4'] [--alpha 90] [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

SIZE = 608
PITCH = 28  # dot spacing in px
DOT = 14  # full-coverage dot size in px
MIN_COVER = 0.3  # skip cells the logo barely touches
SS = 4  # supersampling factor
CLI_SCALE = 0.35  # must match SCALE in logo-pty.py

# Pinned so a rebuild always gets the same shapes.
SOURCES = {
    "claude": "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/claude.svg",
    "devin": "https://devin.ai/favicon.svg",
    "ghostty": "https://raw.githubusercontent.com/ghostty-org/ghostty/c4bec781b0697477b4f38c703b453875a6a1c74b/"
    "macos/Assets.xcassets/Custom%20Icon/CustomIconGhost.imageset/ghosty.png",
}

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


def default_out() -> Path:
    data = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data) / "terminal-logos"


def hex_color(s: str) -> RGB:
    s = s.lstrip("#")
    try:
        if len(s) != 6:
            raise ValueError
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected #rrggbb, got {s!r}") from None


def alpha(s: str) -> int:
    v = int(s)
    if not 0 <= v <= 255:
        raise argparse.ArgumentTypeError(f"expected 0-255, got {v}")
    return v


def fetch_source(name: str, src_dir: Path) -> Path:
    url = SOURCES[name]
    path = src_dir / (name + Path(url).suffix)
    if not path.exists():
        print(f"fetching {name} logo from {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "terminal-logos"})  # noqa: S310 - fixed https URLs
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            path.write_bytes(r.read())
    return path


def fit(mask: Image.Image, margin: int = 0) -> Image.Image:
    """Crop to the shape and scale it to fill a SIZE x SIZE canvas, centered."""
    mask = mask.crop(mask.getbbox())
    k = (SIZE - margin) / max(mask.size)
    mask = mask.resize((round(mask.width * k), round(mask.height * k)), Image.LANCZOS)
    out = Image.new("L", (SIZE, SIZE))
    out.paste(mask, ((SIZE - mask.width) // 2, (SIZE - mask.height) // 2))
    return out


def svg_mask(path: Path) -> Image.Image:
    # pymupdf has self-contained wheels, unlike cairosvg, so `uv run` needs no system libraries.
    import pymupdf

    page = pymupdf.open(path)[0]
    k = 2 * SIZE / max(page.rect.width, page.rect.height)  # oversample, fit() scales down
    pix = page.get_pixmap(matrix=pymupdf.Matrix(k, k), alpha=True)
    a = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples).getchannel("A")
    return fit(a).point(lambda v: 255 if v > 10 else 0)


def ghostty_mask(path: Path) -> Image.Image:
    # Official ghost (ghostty-org/ghostty macos/.../CustomIconGhost.imageset/ghosty.png):
    # light body, dark ">-" face cut out as holes, soft glow dropped.
    im = Image.open(path).convert("LA")
    body = ImageChops.multiply(
        im.getchannel("A").point(lambda v: 255 if v > 200 else 0),
        im.getchannel("L").point(lambda v: 255 if v > 150 else 0),
    )
    return fit(body, margin=48).point(lambda v: 255 if v > 127 else 0)


def opencode_mask() -> Image.Image:
    # Official mark (sst/opencode packages/identity/mark.svg, 512 viewBox): a 256x320
    # frame with a 128x192 window and a gray block filling the window's lower half.
    im = Image.new("L", (SIZE, SIZE))
    d = ImageDraw.Draw(im)
    k = SIZE / 352  # fit the 320-tall mark with a little margin

    def box(x0: int, y0: int, x1: int, y1: int) -> list[int]:
        return [round((x0 - 80) * k), round((y0 - 80) * k), round((x1 - 80) * k) - 1, round((y1 - 80) * k) - 1]

    d.rectangle(box(128, 96, 384, 416), fill=255)
    d.rectangle(box(192, 160, 320, 352), fill=0)
    d.rectangle(box(192, 224, 320, 352), fill=110)
    return im


def codex_mask() -> Image.Image:
    # ">_" prompt glyph, the mark codex shows in its own banner.
    im = Image.new("L", (SIZE, SIZE))
    d = ImageDraw.Draw(im)
    d.line([(70, 170), (250, 304), (70, 438)], fill=255, width=64, joint="curve")
    d.rectangle([300, 414, 300 + 9 * PITCH - 1, 414 + 2 * PITCH - 1], fill=255)  # whole dots: 9 x 2
    return im


def dotted(mask: Image.Image, color: RGBA, pitch: int = PITCH, dot: int = DOT) -> Image.Image:
    # Coverage of every pitch x pitch cell at every grid offset, via a summed-area table.
    m = np.asarray(mask, dtype=np.float64) / 255
    on = (m > 0.08).astype(np.float64)
    s_on, s_m = (np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1) for a in (on, m))

    def box(t: np.ndarray, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        return t[y + pitch, x + pitch] - t[y, x + pitch] - t[y + pitch, x] + t[y, x]

    def cells(oy: int, ox: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        ys = np.arange(oy - pitch, mask.height, pitch)
        xs = np.arange(ox - pitch, mask.width, pitch)
        ys, xs = ys[(ys >= 0) & (ys + pitch <= mask.height)], xs[(xs >= 0) & (xs + pitch <= mask.width)]
        y, x = np.meshgrid(ys, xs, indexing="ij")
        return y, x, box(s_on, y, x) / pitch**2, box(s_m, y, x)

    # Halftone: a dot's area follows its cell's coverage, so edge cells get smaller dots and
    # the outline survives. Pick the grid offset with the fewest half-covered cells (crispest
    # edges), and drop near-empty cells so stray specks don't blur the silhouette.
    def err(o: tuple[int, int]) -> float:
        cov = cells(*o)[2]
        return float((cov * (1 - cov)).sum())

    best = min(((oy, ox) for oy in range(pitch) for ox in range(pitch)), key=err)
    ys, xs, cov, tot = cells(*best)

    # Draw at SS x and downsample so small dots stay sharp-edged when the terminal scales the image.
    big = Image.new("RGBA", (mask.width * SS, mask.height * SS))
    d = ImageDraw.Draw(big)
    for y, x, c, t in zip(ys.ravel(), xs.ravel(), cov.ravel(), tot.ravel()):
        if c < MIN_COVER:
            continue
        side = dot * SS * c**0.5
        # Centre the dot on the covered part of the cell (its centroid), so edge dots sit
        # inside the shape instead of straddling its outline.
        cy_on, cx_on = np.nonzero(on[y : y + pitch, x : x + pitch])
        cx, cy = (x + cx_on.mean() + 0.5) * SS, (y + cy_on.mean() + 0.5) * SS
        a = min(1.0, t / (c * pitch**2))  # keep partly-lit areas (opencode's gray block) dimmer
        d.rectangle(
            [cx - side / 2, cy - side / 2, cx + side / 2 - 1, cy + side / 2 - 1],
            fill=(*color[:3], round(color[3] * a)),
        )
    # Safety net: trim any leftover sliver of dot ink outside the silhouette.
    clip = mask.point(lambda v: 255 if v > 20 else 0).resize(big.size, Image.NEAREST)
    big.putalpha(ImageChops.multiply(big.getchannel("A"), clip))
    return big.resize(mask.size, Image.LANCZOS)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bg", type=hex_color, default="#1e1e2e", help="terminal background (default: Catppuccin Mocha)")
    p.add_argument("--fg", type=hex_color, default="#cdd6f4", help="dot color (default: %(default)s)")
    p.add_argument("--alpha", type=alpha, default=90, help="dot opacity 0-255; low keeps text readable (default: 90)")
    p.add_argument("--out", type=Path, default=default_out(), help="output directory (default: %(default)s)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bg: RGBA = (*args.bg, 255)
    color: RGBA = (*args.fg, args.alpha)
    src_dir = args.out / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)

    masks = {
        "claude": svg_mask(fetch_source("claude", src_dir)),
        "devin": svg_mask(fetch_source("devin", src_dir)),
        "opencode": opencode_mask(),
        "codex": codex_mask(),
    }
    for name, mask in masks.items():
        img = Image.new("RGBA", (SIZE, SIZE), bg)
        img.alpha_composite(dotted(mask, color))
        img.save(args.out / f"{name}-logo-faint.png")

    # Ghostty's background-image is fit to the pane's shorter side, so pad the ghost to the same
    # fraction the CLI logos use. That way it sits exactly under (and is hidden by) a CLI logo.
    side = round(SIZE / CLI_SCALE)
    img = Image.new("RGBA", (side, side), bg)
    # Finer grid than the CLI logos: the ghost's ">-" face is too thin to read at PITCH.
    ghost = dotted(ghostty_mask(fetch_source("ghostty", src_dir)), color, pitch=20, dot=10)
    img.alpha_composite(ghost, ((side - SIZE) // 2, (side - SIZE) // 2))
    img.save(args.out / "ghostty-logo-bg.png")

    # Solid square logo-pty.py stretches behind each CLI logo to hide the ghost at the edges.
    Image.new("RGBA", (4, 4), bg).save(args.out / "logo-backing.png")
    print(f"wrote logos to {args.out}")


if __name__ == "__main__":
    main()
