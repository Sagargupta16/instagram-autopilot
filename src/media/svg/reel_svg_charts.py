"""The stat Reel's chart variants and headline badge: ranked bars and a line over time.

Both start at VISUAL_S, under the headline, so the chart is already moving in the first
second. Bars are boxy solids that grow with a lit top face and a shaded end face; the line
draws over a soft copy of itself set back and down, so it reads as a ribbon above the axis.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from src.media.svg.reel_svg_count import number
from src.media.svg.svg_kit import (
    LEFT,
    RIGHT,
    SMALL_PX,
    TRAVEL,
    Canvas,
    LayoutError,
    fmt,
    text_width,
)
from src.media.svg.svg_parts import icon, tile
from src.media.svg.svg_solid import bar_faces

VISUAL_S = 0.4  # the stat visual starts this early, under the headline
CHART_PX, VALUE_PX, ROW_ICON = 34, 38, 88  # bar text, line end values, icon beside a chart
SHADOW = (10, 14)  # the line's set-back copy: x and y offset


def badge(canvas: Canvas, name: str, cx: float, cy: float, size: float, at: float) -> str:
    """The headline icon on its tile, popping in at `at`."""
    body = tile(canvas, cx, cy, 0.56 * size)
    body += icon(name, cx - size / 2, cy - size / 2, size, canvas.look.accent)
    pop = [(at, "0"), (at + 0.3, "1.12"), (at + 0.55, "1")]
    return canvas.scaled(cx, cy, pop, body)


def _head_row(canvas: Canvas, scene: dict[str, Any], top: float) -> tuple[list[str], float]:
    """Unit on the left and the headline icon on the right, above bars or a line."""
    out = []
    height = 64 if scene.get("unit") else 0
    if scene.get("icon"):
        height = 2 * 0.56 * ROW_ICON + 18
        cx, cy = RIGHT - 0.56 * ROW_ICON, top + 0.56 * ROW_ICON
        out.append(badge(canvas, scene["icon"], cx, cy, ROW_ICON, VISUAL_S - 0.2))
    if scene.get("unit"):
        y = top + height / 2 - 18 + 29 if scene.get("icon") else top + 29
        unit = canvas.text(LEFT, y, scene["unit"], SMALL_PX, canvas.look.muted)
        out.append(canvas.reveal([unit], VISUAL_S))
    return out, top + height


def bars(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    look = canvas.look
    ranked = sorted(scene["bars"], key=lambda bar: number(bar["value"]), reverse=True)
    out, top = _head_row(canvas, scene, top)
    row = min(104.0, (bottom - top + 20) / len(ranked))
    if row < 92:
        raise LayoutError("the bars do not fit; use fewer bars or a shorter headline")
    peak = max(number(bar["value"]) for bar in ranked) or 1.0
    for i, bar in enumerate(ranked):
        y = top + i * row
        label_w = text_width(bar["label"], CHART_PX, bold=True) + text_width(
            bar["value"], CHART_PX, bold=True
        )
        if label_w + 24 > RIGHT - LEFT:
            raise LayoutError("a bar label and value do not fit on one line")
        start = VISUAL_S + i * 0.55
        span = max(16.0, (RIGHT - LEFT - 12) * number(bar["value"]) / peak)  # room for the end
        width = fmt(span)
        texts = [
            canvas.text(LEFT, y + 32, bar["label"], CHART_PX, look.text, bold=True),
            canvas.text(
                RIGHT, y + 32, bar["value"], CHART_PX, look.accent_text, bold=True, anchor="end"
            ),
        ]
        track = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="{RIGHT - LEFT}" height="32" rx="6" '
            f'fill="{look.track}" fill-opacity="0.45"/>'
        )
        grow = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="0" height="32" rx="6" fill="{look.accent}">'
            + canvas.anim("width", [(start, "0"), (start + 0.6, width)], ease=TRAVEL)
            + "</rect>"
        )
        faces = bar_faces(canvas, LEFT, y + 52, 32, span, (start, 0.6))
        out += [track, grow, faces, canvas.reveal(texts, start)]
    return out


def line(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    look = canvas.look
    points = scene["points"]
    out, top = _head_row(canvas, scene, top)
    y0, y1 = top + 70, bottom - 64
    if y1 - y0 < 240:
        raise LayoutError("the line chart does not fit; shorten the headline or takeaway")
    values = [number(point["value"]) for point in points]
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    x0, x1 = LEFT + 40, RIGHT - 40
    xy = [
        (x0 + (x1 - x0) * i / (len(points) - 1), y1 - (y1 - y0) * (v - low) / span)
        for i, v in enumerate(values)
    ]
    legs = [math.dist(a, b) for a, b in pairwise(xy)]
    total, draw = sum(legs) or 1.0, 3.0
    dash = fmt(total + 4)
    path = "M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y in xy)
    out.append(
        f'<line x1="{LEFT}" y1="{fmt(y1 + 24)}" x2="{RIGHT}" y2="{fmt(y1 + 24)}" '
        f'stroke="{look.muted}" stroke-width="3"/>'
    )
    drawing = canvas.anim(
        "stroke-dashoffset", [(VISUAL_S, dash), (VISUAL_S + draw, "0")], ease=TRAVEL
    )
    for (dx, dy), opacity in ((SHADOW, "0.25"), ((0, 0), "1")):
        out.append(
            f'<path d="{path}" transform="translate({dx} {dy})" fill="none" '
            f'stroke="{look.accent}" stroke-opacity="{opacity}" stroke-width="8" '
            f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}" '
            f'stroke-dashoffset="{dash}">{drawing}</path>'
        )
    spacing = (x1 - x0) / (len(points) - 1)
    widest = max(text_width(point["label"], SMALL_PX) for point in points)
    every = 1.5 * widest + 16 < spacing  # an edge label hangs fully to one side of its point
    reached = 0.0
    for i, ((x, y), point) in enumerate(zip(xy, points, strict=True)):
        at = VISUAL_S + draw * reached / total
        reached += legs[i] if i < len(legs) else 0
        mark = [f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="11" fill="{look.accent}"/>']
        edge = i in (0, len(points) - 1)
        anchor = {0: "start", len(points) - 1: "end"}.get(i, "middle")
        if every or edge:
            mark.append(
                canvas.text(x, y1 + 80, point["label"], SMALL_PX, look.muted, anchor=anchor)
            )
        if edge:
            value = canvas.text(
                x, y - 32, point["value"], VALUE_PX, look.text, bold=True, anchor=anchor
            )
            mark.append(value)
        out.append(canvas.reveal(mark, at))
    return out
