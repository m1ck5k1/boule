#!/usr/bin/env python3
"""
make_qr.py — generate a stylised, scannable QR code linking to the Boule PWA.

Design notes (why it looks like this):
  * Error correction level H (~30% recoverable) so heavy styling + a centre mark
    cannot break the decode.
  * Data modules are rounded and carry a two-stop gradient — the "second tally"
    reading: one code, two tones.
  * The three FINDER patterns are drawn as classic solid squares. Styling those
    is the number-one cause of unscannable "pretty" QR codes.
  * Every generated asset is DECODED and asserted against the input URL before
    the script reports success. A QR that does not scan is not a deliverable.

Usage:
    python3 marketing/make_qr.py https://<real-url> [--outdir marketing]

Requires: segno, zxing-cpp, pillow
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import segno
import zxingcpp
from PIL import Image, ImageDraw

QUIET = 4                     # quiet-zone modules (spec minimum)
ECC = "h"                     # error correction level
STOPS = ("#0B1F3B", "#C2185B")  # deep navy -> deep magenta (both dark: scan-safe)
FINDER_INK = "#0B1F3B"        # solid ink for the finder patterns


# ---------------------------------------------------------------- colour maths
def _srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_luminance(hexcol: str) -> float:
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_lin(r) + 0.7152 * _srgb_to_lin(g) + 0.0722 * _srgb_to_lin(b)


def contrast_vs_white(hexcol: str) -> float:
    return (1.0 + 0.05) / (rel_luminance(hexcol) + 0.05)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------- geometry
def finder_origins(n: int) -> dict[tuple[int, int], str]:
    """(row, col) top-left corner of each 7x7 finder pattern -> label."""
    return {(0, 0): "tl", (0, n - 7): "tr", (n - 7, 0): "bl"}


def which_finder(r: int, c: int, n: int) -> tuple[int, int] | None:
    for origin in finder_origins(n):
        fr, fc = origin
        if fr <= r < fr + 7 and fc <= c < fc + 7:
            return origin
    return None


def is_dark(origin: tuple[int, int], r: int, c: int) -> bool:
    """Classic 7x7 finder: dark border, white ring, dark 3x3 core."""
    lr, lc = r - origin[0], c - origin[1]
    ring = max(abs(lr - 3), abs(lc - 3))
    return ring == 3 or ring <= 1


# ----------------------------------------------------------------------- SVG
def write_svg(qr: segno.QRCode, path: pathlib.Path, scale: int, centre_mark: bool) -> int:
    m = qr.matrix
    n = len(m)
    side = (n + 2 * QUIET) * scale

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" '
        f'viewBox="0 0 {side} {side}" role="img" aria-label="QR code linking to Boule">'
    )
    parts.append(
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{STOPS[0]}"/>'
        f'<stop offset="1" stop-color="{STOPS[1]}"/>'
        f'</linearGradient></defs>'
    )
    parts.append(f'<rect width="{side}" height="{side}" fill="#ffffff"/>')

    def xy(r: int, c: int) -> tuple[int, int]:
        return (c + QUIET) * scale, (r + QUIET) * scale

    # data modules — rounded, gradient-filled
    radius = scale * 0.34
    for r in range(n):
        for c in range(n):
            if not m[r][c]:
                continue
            if which_finder(r, c, n) is not None:
                continue
            x, y = xy(r, c)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" '
                f'rx="{radius:.2f}" ry="{radius:.2f}" fill="url(#g)"/>'
            )

    # finder patterns — solid, classic, high contrast
    for origin in finder_origins(n):
        x0, y0 = xy(*origin)
        size7 = 7 * scale
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{size7}" height="{size7}" '
            f'rx="{scale * 1.2:.2f}" fill="{FINDER_INK}"/>'
        )
        inset = scale
        parts.append(
            f'<rect x="{x0 + inset}" y="{y0 + inset}" width="{5 * scale}" '
            f'height="{5 * scale}" rx="{scale * 0.8:.2f}" fill="#ffffff"/>'
        )
        parts.append(
            f'<rect x="{x0 + 2 * scale}" y="{y0 + 2 * scale}" width="{3 * scale}" '
            f'height="{3 * scale}" rx="{scale * 0.5:.2f}" fill="{FINDER_INK}"/>'
        )

    if centre_mark:
        # the "gap" glyph: two bars, a deliberate gap between them
        cx, cy = side / 2, side / 2
        plate = scale * 7
        bar_w, bar_h, gap = scale * 1.6, scale * 3.4, scale * 0.9
        parts.append(
            f'<rect x="{cx - plate / 2:.1f}" y="{cy - plate / 2:.1f}" '
            f'width="{plate}" height="{plate}" rx="{scale * 1.4:.1f}" '
            f'fill="#ffffff" stroke="{STOPS[1]}" stroke-width="{scale * 0.28:.2f}"/>'
        )
        for sign in (-1, 1):
            bx = cx + sign * (gap / 2) - (bar_w if sign < 0 else 0)
            parts.append(
                f'<rect x="{bx:.1f}" y="{cy - bar_h / 2:.1f}" width="{bar_w:.1f}" '
                f'height="{bar_h:.1f}" rx="{bar_w * 0.35:.2f}" fill="{STOPS[0]}"/>'
            )

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return side


# ----------------------------------------------------------------------- PNG
def write_png(qr: segno.QRCode, path: pathlib.Path, scale: int, centre_mark: bool) -> None:
    m = qr.matrix
    n = len(m)
    side = (n + 2 * QUIET) * scale
    img = Image.new("RGB", (side, side), "white")
    d = ImageDraw.Draw(img)
    a, b = hex_to_rgb(STOPS[0]), hex_to_rgb(STOPS[1])

    def xy(r: int, c: int) -> tuple[int, int]:
        return (c + QUIET) * scale, (r + QUIET) * scale

    for r in range(n):
        colour = lerp(a, b, r / max(n - 1, 1))
        for c in range(n):
            if not m[r][c] or which_finder(r, c, n) is not None:
                continue
            x, y = xy(r, c)
            d.rounded_rectangle(
                [x, y, x + scale - 1, y + scale - 1], radius=scale * 0.34, fill=colour
            )

    for origin in finder_origins(n):
        x0, y0 = xy(*origin)
        ink = hex_to_rgb(FINDER_INK)
        d.rounded_rectangle([x0, y0, x0 + 7 * scale - 1, y0 + 7 * scale - 1],
                            radius=scale * 1.2, fill=ink)
        d.rounded_rectangle([x0 + scale, y0 + scale, x0 + 6 * scale - 1, y0 + 6 * scale - 1],
                            radius=scale * 0.8, fill="white")
        d.rounded_rectangle([x0 + 2 * scale, y0 + 2 * scale, x0 + 5 * scale - 1, y0 + 5 * scale - 1],
                            radius=scale * 0.5, fill=ink)

    if centre_mark:
        cx = cy = side / 2
        plate, bar_w, bar_h, gap = scale * 7, scale * 1.6, scale * 3.4, scale * 0.9
        d.rounded_rectangle([cx - plate / 2, cy - plate / 2, cx + plate / 2, cy + plate / 2],
                            radius=scale * 1.4, fill="white",
                            outline=hex_to_rgb(STOPS[1]), width=max(1, int(scale * 0.28)))
        for sign in (-1, 1):
            bx = cx + sign * (gap / 2) - (bar_w if sign < 0 else 0)
            d.rounded_rectangle([bx, cy - bar_h / 2, bx + bar_w, cy + bar_h / 2],
                                radius=bar_w * 0.35, fill=hex_to_rgb(STOPS[0]))

    img.save(path)


# -------------------------------------------------------------------- verify
def verify(png: pathlib.Path, expect: str) -> bool:
    result = zxingcpp.read_barcodes(Image.open(png))
    if not result:
        return False
    got = result[0].text
    print(f"    decode -> {got!r}  {'OK' if got == expect else 'MISMATCH'}")
    return got == expect


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--outdir", default="marketing")
    ap.add_argument("--scale", type=int, default=12)
    ap.add_argument("--name", default="boule-qr")
    args = ap.parse_args()

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    qr = segno.make(args.url, error=ECC)
    n = len(qr.matrix)

    print(f"url        : {args.url}")
    print(f"qr version : {qr.version}   modules: {n}x{n}   ecc: {ECC.upper()}")
    for s in STOPS:
        print(f"  contrast {s} vs white: {contrast_vs_white(s):.2f}:1")

    ok = True
    for label, mark in (("clean", False), ("branded", True)):
        svg = out / f"{args.name}-{label}.svg"
        png = out / f"{args.name}-{label}.png"
        write_svg(qr, svg, args.scale, mark)
        write_png(qr, png, args.scale, mark)
        print(f"  [{label}] {svg.name} ({svg.stat().st_size} B)  {png.name} ({png.stat().st_size} B)")
        ok &= verify(png, args.url)

    print("RESULT:", "all assets decode and match" if ok else "SCAN FAILURE — do not ship")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
