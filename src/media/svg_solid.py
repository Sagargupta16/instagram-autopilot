"""Solid-looking shapes for SVG Reels, made from 2D SMIL: coin-thick icon tiles, a big number
that extrudes toward the viewer when its count-up lands, and bars with a top and an end face.

Depth always falls down and to the right, as if lit from the top left. The extrusion copies
are the look's accent text color at full opacity, which the palette already checks at 4.5:1
on the background; the faces and tile bases are decoration below 50% opacity.
"""

from __future__ import annotations

from src.media.svg_kit import TRAVEL, Canvas, fmt
from src.media.svg_parts import tile

COIN = 10  # px a tile's base sits below it
EXTRUDE = (8, 2.0, 2.6)  # copies behind a big number, and the x and y step of each copy
FACE = 10  # px depth of a bar's top and end faces


def coin(canvas: Canvas, cx: float, cy: float, radius: float) -> str:
    """The tile's thickness: a fainter copy just below, so a popping tile seems to lift."""
    return tile(canvas, cx, cy + COIN, radius, opacity=0.1)


def extruded(canvas: Canvas, x: float, baseline: float, value: str, size: float, at: float) -> str:
    """Copies of `value` behind its face that slide out to depth at `at`, deepest first."""
    copies, step_x, step_y = EXTRUDE
    out = []
    for k in range(copies, 0, -1):
        shown = canvas.anim("opacity", [(at, "0"), (at + 0.12, "1")])
        slide = canvas.anim(
            "transform",
            [(at, "0 0"), (at + 0.6, f"{fmt(k * step_x)} {fmt(k * step_y)}")],
            tag="animateTransform",
            extra='type="translate" ',
        )
        text = canvas.text(
            x, baseline, value, size, canvas.look.accent_text, bold=True, anchor="middle"
        )
        out.append(f'<g opacity="0">{shown}{slide}{text}</g>')
    return "".join(out)


def extrusion_room() -> float:
    """Extra width the deepest copy needs to the right of the face."""
    copies, step_x, _ = EXTRUDE
    return copies * step_x


def bar_faces(
    canvas: Canvas, x: float, y: float, height: float, width: float, window: tuple[float, float]
) -> str:
    """A growing bar's lit top face and shaded end face, growing with it over `window`."""
    look = canvas.look
    start, seconds = window

    def top(w: float) -> str:
        return (
            f"{fmt(x)},{fmt(y)} {fmt(x + FACE)},{fmt(y - FACE)} "
            f"{fmt(x + w + FACE)},{fmt(y - FACE)} {fmt(x + w)},{fmt(y)}"
        )

    def end(w: float) -> str:
        return (
            f"{fmt(x + w)},{fmt(y)} {fmt(x + w + FACE)},{fmt(y - FACE)} "
            f"{fmt(x + w + FACE)},{fmt(y + height - FACE)} {fmt(x + w)},{fmt(y + height)}"
        )

    shown = canvas.anim("opacity", [(start, "0"), (start + 0.08, "1")])  # nothing before it grows
    out = []
    for shape, paint in ((top, look.accent_text), (end, look.accent)):
        grow = canvas.anim(
            "points", [(start, shape(0)), (start + seconds, shape(width))], ease=TRAVEL
        )
        out.append(
            f'<polygon points="{shape(0)}" fill="{paint}" fill-opacity="0.45">{grow}</polygon>'
        )
    return f'<g opacity="0">{shown}{"".join(out)}</g>'
