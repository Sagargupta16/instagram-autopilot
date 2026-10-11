"""One stat story per Reel: a big-number count-up, ranked bars, a percent ring or a line.

One clock: headline 0-2 s, the visual reveal, its context, the takeaway with the source
line, then a hold of at least 3 s (12 s minimum overall).
"""

from __future__ import annotations

import math
import re
from itertools import pairwise
from typing import Any

from src.media.svg_kit import (
    ACCENT,
    ACCENT_TEXT,
    LEFT,
    MUTED,
    RIGHT,
    RISE,
    SAFE,
    TEXT,
    TRACK,
    Canvas,
    LayoutError,
    block_height,
    fit,
    fmt,
    header,
    takeaway,
    takeaway_height,
    text_width,
)

HEAD_S, COUNT_S, STEPS = 2.0, 2.4, 24
_VALUE = re.compile(r"^(?P<cur>[^\d]?)(?P<num>[\d,]+)(?P<dec>\.\d+)?(?P<suf>.*)$")


def number(value: str) -> float:
    """The magnitude used for scaling; suffix multipliers keep mixed bars comparable."""
    m = _VALUE.match(value)
    base = float(m["num"].replace(",", "") + (m["dec"] or "")) if m else 0.0
    suffix = (m["suf"] if m else "").strip().casefold()
    scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
    return base * scale.get(suffix, 1e12 if suffix in {"tn", "trillion"} else 1.0)


def counting(value: str, steps: int = STEPS) -> list[str]:
    """Count-up frames that share the final value's prefix, grouping, decimals and suffix."""
    m = _VALUE.match(value)
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
        element = canvas.text(x, y, label, size, TEXT, bold=True, anchor="middle")
        out.append(f'<g opacity="0">{canvas.anim("opacity", shown, discrete=True)}{element}</g>')
    return "".join(out)


def _context(canvas: Canvas, top: float, text: str, start: float) -> tuple[str, float]:
    size, lines = fit(text, (44, 40), RIGHT - LEFT, 3)
    texts, bottom = canvas.lines(LEFT, top, lines, size, MUTED)
    return canvas.reveal(texts, start), bottom


def _context_height(text: str) -> float:
    size, lines = fit(text, (44, 40), RIGHT - LEFT, 3)
    return block_height(len(lines), size)


def _big_number(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    value = scene["value"]
    size = min(240.0, (RIGHT - LEFT) / text_width(value, 1, bold=True))
    if size < 120:
        raise LayoutError("the stat value is too long to show large; shorten it")
    unit_h = 64 if scene.get("unit") else 0
    height = 1.05 * size + 40 + unit_h + _context_height(scene["context"])
    if height > bottom - top:
        raise LayoutError("the stat context does not fit; shorten it")
    top += (bottom - top - height) / 2
    baseline = top + 0.8 * size
    out = [_counter(canvas, 540, baseline, value, size, HEAD_S)]
    y = baseline + 0.25 * size + 40
    if unit_h:
        unit = canvas.text(540, y + 32, scene["unit"], 40, ACCENT_TEXT, bold=True, anchor="middle")
        out.append(canvas.reveal([unit], HEAD_S + COUNT_S))
        y += unit_h
    context, _ = _context(canvas, y, scene["context"], HEAD_S + COUNT_S + 0.2)
    return [*out, context]


def _ring(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
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
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{TRACK}" '
        'stroke-width="44" stroke-opacity="0.45"/>'
    )
    arc = (
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{ACCENT}" '
        f'stroke-width="44" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}" transform="rotate(-90 540 {fmt(cy)})">'
        + canvas.anim("stroke-dashoffset", [(HEAD_S, dash), (HEAD_S + COUNT_S, rest)])
        + "</circle>"
    )
    inner = min(130.0, (2 * radius - 120) / text_width(scene["value"], 1, bold=True))
    counter = _counter(canvas, 540, cy + 0.36 * inner, scene["value"], inner, HEAD_S)
    context, _ = _context(canvas, cy + radius + 56, scene["context"], HEAD_S + COUNT_S + 0.2)
    return [track, arc, counter, context]


def _bars(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    bars = sorted(scene["bars"], key=lambda bar: number(bar["value"]), reverse=True)
    out = []
    if scene.get("unit"):
        out.append(canvas.reveal([canvas.text(LEFT, top + 29, scene["unit"], 36, MUTED)], HEAD_S))
        top += 64
    row = 104
    if top + row * len(bars) - 20 > bottom:
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
            canvas.text(LEFT, y + 32, bar["label"], 40, TEXT, bold=True),
            canvas.text(RIGHT, y + 32, bar["value"], 40, ACCENT_TEXT, bold=True, anchor="end"),
        ]
        track = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="{RIGHT - LEFT}" height="32" rx="16" '
            f'fill="{TRACK}" fill-opacity="0.45"/>'
        )
        grow = (
            f'<rect x="{LEFT}" y="{fmt(y + 52)}" width="0" height="32" rx="16" fill="{ACCENT}">'
            + canvas.anim("width", [(start, "0"), (start + 0.6, width)])
            + "</rect>"
        )
        out += [track, grow, canvas.reveal(texts, start)]
    return out


def _line(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    points = scene["points"]
    out = []
    if scene.get("unit"):
        out.append(canvas.reveal([canvas.text(LEFT, top + 29, scene["unit"], 36, MUTED)], HEAD_S))
        top += 64
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
        f'stroke="{MUTED}" stroke-width="3"/>'
    )
    out.append(
        f'<path d="{path}" fill="none" stroke="{ACCENT}" stroke-width="8" stroke-linecap="round" '
        f'stroke-linejoin="round" stroke-dasharray="{dash}" stroke-dashoffset="{dash}">'
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
        mark = [f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="11" fill="{ACCENT}"/>']
        edge = i in (0, len(points) - 1)
        anchor = "start" if i == 0 else "end" if i == len(points) - 1 else "middle"
        if every or edge:
            mark.append(canvas.text(x, y1 + 80, point["label"], 36, MUTED, anchor=anchor))
        if edge:
            mark.append(canvas.text(x, y - 32, point["value"], 44, TEXT, bold=True, anchor=anchor))
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


def compose(
    canvas: Canvas, scene: dict[str, Any], source_line: str | None, *, kicker: bool = True
) -> list[str]:
    parts, top = header(canvas, "BY THE NUMBERS" if kicker else None, scene["headline"])
    source_h = 38 + 28 if source_line else 0
    take_h = takeaway_height(scene["takeaway"])
    limit = SAFE[3] - RISE
    take_top = limit - source_h - take_h
    visual = VARIANTS[scene["variant"]](canvas, scene, top + 56, take_top - 40)
    take_at = HEAD_S + reveal_seconds(scene)
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at)
    parts += [*visual, card]
    if source_line:
        line = canvas.text(LEFT, card_bottom + 28 + 29, source_line, 36, MUTED)
        parts.append(canvas.reveal([line], take_at + 0.3))
    return parts
