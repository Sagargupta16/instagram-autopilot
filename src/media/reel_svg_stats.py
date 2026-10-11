"""One stat story per Reel: a big-number count-up, ranked bars, a percent ring or a line.

One clock: headline 0-2 s, the visual reveal, its context, the takeaway with the source
line, then a hold of at least 4 s whose last 2 s are the end card (12 s minimum overall).
The optional headline icon sits above the number, inside the ring, or beside the unit.
"""

from __future__ import annotations

import math
import re
from itertools import pairwise
from typing import Any

from src.media.svg_kit import (
    LEFT,
    RIGHT,
    RISE,
    SAFE,
    Canvas,
    LayoutError,
    block_height,
    fit,
    fmt,
    text_width,
)
from src.media.svg_parts import header, icon, takeaway, takeaway_height, tile

HEAD_S, COUNT_S, STEPS, TAKE_S = 2.0, 2.4, 24, 1.3
BIG_ICON, ROW_ICON = 120, 88
_VALUE = re.compile(r"(?P<cur>\D?)(?P<num>[\d,]+)(?P<dec>\.\d+)?(?P<suf>\D*)")


def number(value: str) -> float:
    """The magnitude used for scaling; suffix multipliers keep mixed bars comparable."""
    m = _VALUE.fullmatch(value)
    base = float(m["num"].replace(",", "") + (m["dec"] or "")) if m else 0.0
    suffix = (m["suf"] if m else "").strip().casefold()
    scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
    return base * scale.get(suffix, 1e12 if suffix in {"tn", "trillion"} else 1.0)


def counting(value: str, steps: int = STEPS) -> list[str]:
    """Count-up frames that share the final value's prefix, grouping, decimals and suffix."""
    m = _VALUE.fullmatch(value)
    if not m:
        return [value]
    final = float(m["num"].replace(",", "") + (m["dec"] or ""))
    decimals = len(m["dec"]) - 1 if m["dec"] else 0
    grouping = "," if "," in m["num"] else ""
    frames = []
    for j in range(1, steps):
        current = final * (1 - (1 - j / steps) ** 3)
        frames.append(f"{m['cur']}{current:{grouping}.{decimals}f}{m['suf']}")
    return [*frames, value]


def _counter(canvas: Canvas, x: float, y: float, value: str, size: float, start: float) -> str:
    """Discrete count-up: each frame is its own text shown for one tick."""
    frames = counting(value)
    tick = COUNT_S / len(frames)
    out = []
    for j, label in enumerate(frames):
        shown = [(0.0, "0"), (start + j * tick, "1")]
        if j < len(frames) - 1:
            shown.append((start + (j + 1) * tick, "0"))
        element = canvas.text(x, y, label, size, canvas.look.text, bold=True, anchor="middle")
        out.append(f'<g opacity="0">{canvas.anim("opacity", shown, discrete=True)}{element}</g>')
    return "".join(out)


def _badge(canvas: Canvas, name: str, cx: float, cy: float, size: float, at: float) -> str:
    """The headline icon on its tile, popping in at `at`."""
    body = tile(canvas, cx, cy, 0.56 * size)
    body += icon(name, cx - size / 2, cy - size / 2, size, canvas.look.accent)
    pop = [(at, "0"), (at + 0.3, "1.12"), (at + 0.55, "1")]
    return canvas.scaled(cx, cy, pop, body)


def _context(canvas: Canvas, top: float, text: str, start: float) -> tuple[str, float]:
    size, lines = fit(text, (44, 40), RIGHT - LEFT, 3)
    texts, bottom = canvas.lines(LEFT, top, lines, size, canvas.look.muted)
    return canvas.reveal(texts, start), bottom


def _context_height(text: str) -> float:
    size, lines = fit(text, (44, 40), RIGHT - LEFT, 3)
    return block_height(len(lines), size)


def _big_number(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    value, name = scene["value"], scene.get("icon")
    unit_h = 64 if scene.get("unit") else 0
    icon_h = 2 * 0.56 * BIG_ICON + 28 if name else 0
    fixed = 40 + unit_h + icon_h + _context_height(scene["context"])
    size = min(
        240.0, (RIGHT - LEFT) / text_width(value, 1, bold=True), (bottom - top - fixed) / 1.05
    )
    if size < 120:
        raise LayoutError("the stat value or context is too long to show large; shorten it")
    top += (bottom - top - fixed - 1.05 * size) / 2
    out = []
    if name:
        out.append(_badge(canvas, name, 540, top + 0.56 * BIG_ICON, BIG_ICON, HEAD_S - 0.4))
        top += icon_h
    baseline = top + 0.8 * size
    out.append(_counter(canvas, 540, baseline, value, size, HEAD_S))
    y = baseline + 0.25 * size + 40
    if unit_h:
        look = canvas.look
        unit = canvas.text(
            540, y + 32, scene["unit"], 40, look.accent_text, bold=True, anchor="middle"
        )
        out.append(canvas.reveal([unit], HEAD_S + COUNT_S))
        y += unit_h
    context, _ = _context(canvas, y, scene["context"], HEAD_S + COUNT_S + 0.2)
    return [*out, context]


def _ring(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    look = canvas.look
    context_h = _context_height(scene["context"])
    radius = min(210.0, (bottom - top - context_h - 56) / 2)
    if radius < 150:
        raise LayoutError("the ring does not fit; shorten the headline or context")
    top += (bottom - top - (2 * radius + 56 + context_h)) / 2
    cy = top + radius
    share = float(scene["value"].rstrip("%").replace(",", "")) / 100
    circumference = 2 * math.pi * radius
    dash, rest = fmt(circumference), fmt(circumference * (1 - share))
    track = (
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{look.track}" '
        'stroke-width="44" stroke-opacity="0.45"/>'
    )
    arc = (
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{look.accent}" '
        f'stroke-width="44" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}" transform="rotate(-90 540 {fmt(cy)})">'
        + canvas.anim("stroke-dashoffset", [(HEAD_S, dash), (HEAD_S + COUNT_S, rest)])
        + "</circle>"
    )
    inner = min(130.0, (2 * radius - 120) / text_width(scene["value"], 1, bold=True))
    counter = _counter(canvas, 540, cy + 0.36 * inner, scene["value"], inner, HEAD_S)
    out = [track, arc, counter]
    room = radius - 22 - 0.44 * inner - 28  # ring interior above the count-up
    if (name := scene.get("icon")) and room >= 48:
        size = min(80.0, room)
        badge_y = cy - 0.44 * inner - 14 - size / 2
        body = icon(name, 540 - size / 2, badge_y - size / 2, size, look.accent)
        out.append(canvas.reveal([body], HEAD_S - 0.4))
    context, _ = _context(canvas, cy + radius + 56, scene["context"], HEAD_S + COUNT_S + 0.2)
    return [*out, context]


def _head_row(canvas: Canvas, scene: dict[str, Any], top: float) -> tuple[list[str], float]:
    """Unit on the left and the headline icon on the right, above bars or a line."""
    out = []
    height = 64 if scene.get("unit") else 0
    if scene.get("icon"):
        height = 2 * 0.56 * ROW_ICON + 18
        cx, cy = RIGHT - 0.56 * ROW_ICON, top + 0.56 * ROW_ICON
        out.append(_badge(canvas, scene["icon"], cx, cy, ROW_ICON, HEAD_S - 0.4))
    if scene.get("unit"):
        y = top + height / 2 - 18 + 29 if scene.get("icon") else top + 29
        unit = canvas.text(LEFT, y, scene["unit"], 36, canvas.look.muted)
        out.append(canvas.reveal([unit], HEAD_S))
    return out, top + height


def _bars(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    look = canvas.look
    bars = sorted(scene["bars"], key=lambda bar: number(bar["value"]), reverse=True)
    out, top = _head_row(canvas, scene, top)
    row = min(104.0, (bottom - top + 20) / len(bars))
    if row < 92:
        raise LayoutError("the bars do not fit; use fewer bars or a shorter headline")
    peak = max(number(bar["value"]) for bar in bars) or 1.0
    for i, bar in enumerate(bars):
        y = top + i * row
        label_w = text_width(bar["label"], 40, bold=True) + text_width(bar["value"], 40, bold=True)
        if label_w + 24 > RIGHT - LEFT:
            raise LayoutError("a bar label and value do not fit on one line")
        start = HEAD_S + i * 0.55
        width = fmt(max(16.0, (RIGHT - LEFT) * number(bar["value"]) / peak))
        texts = [
            canvas.text(LEFT, y + 32, bar["label"], 40, look.text, bold=True),
            canvas.text(RIGHT, y + 32, bar["value"], 40, look.accent_text, bold=True, anchor="end"),
        ]
        track = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="{RIGHT - LEFT}" height="32" rx="16" '
            f'fill="{look.track}" fill-opacity="0.45"/>'
        )
        grow = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="0" height="32" rx="16" fill="{look.accent}">'
            + canvas.anim("width", [(start, "0"), (start + 0.6, width)])
            + "</rect>"
        )
        out += [track, grow, canvas.reveal(texts, start)]
    return out


def _line(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
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
    out.append(
        f'<path d="{path}" fill="none" stroke="{look.accent}" stroke-width="8" '
        f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}">'
        + canvas.anim("stroke-dashoffset", [(HEAD_S, dash), (HEAD_S + draw, "0")])
        + "</path>"
    )
    spacing = (x1 - x0) / (len(points) - 1)
    widest = max(text_width(point["label"], 36) for point in points)
    every = 1.5 * widest + 16 < spacing  # an edge label hangs fully to one side of its point
    reached = 0.0
    for i, ((x, y), point) in enumerate(zip(xy, points, strict=True)):
        at = HEAD_S + draw * reached / total
        reached += legs[i] if i < len(legs) else 0
        mark = [f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="11" fill="{look.accent}"/>']
        edge = i in (0, len(points) - 1)
        anchor = {0: "start", len(points) - 1: "end"}.get(i, "middle")
        if every or edge:
            mark.append(canvas.text(x, y1 + 80, point["label"], 36, look.muted, anchor=anchor))
        if edge:
            value = canvas.text(x, y - 32, point["value"], 44, look.text, bold=True, anchor=anchor)
            mark.append(value)
        out.append(canvas.reveal(mark, at))
    return out


VARIANTS = {"big_number": _big_number, "ring": _ring, "bars": _bars, "line": _line}


def reveal_seconds(scene: dict[str, Any]) -> float:
    if scene["variant"] == "bars":
        return 0.55 * (len(scene["bars"]) - 1) + 0.6 + 0.8
    if scene["variant"] == "line":
        return 3.0 + 0.8
    return COUNT_S + 2.4


def duration(scene: dict[str, Any]) -> float:
    return max(12.0, round(HEAD_S + reveal_seconds(scene) + 5.5, 1))


def hold_start(scene: dict[str, Any]) -> float:
    """When the takeaway and source line have finished appearing."""
    return HEAD_S + reveal_seconds(scene) + TAKE_S


def compose(
    canvas: Canvas, scene: dict[str, Any], source_line: str | None, *, kicker: bool = True
) -> list[str]:
    look = canvas.look
    parts, top = header(canvas, look.kicker("stat") if kicker else None, scene["headline"])
    source_h = 38 + 28 if source_line else 0
    take_h = takeaway_height(scene["takeaway"])
    limit = SAFE[3] - RISE
    take_top = limit - source_h - take_h
    visual = VARIANTS[scene["variant"]](canvas, scene, top + 48, take_top - 40)
    take_at = HEAD_S + reveal_seconds(scene)
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at)
    parts += [*visual, card]
    if source_line:
        line = canvas.text(LEFT, card_bottom + 28 + 29, source_line, 36, look.muted)
        parts.append(canvas.reveal([line], take_at + 0.3))
    return parts
