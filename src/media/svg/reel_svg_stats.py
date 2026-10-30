"""One stat story per Reel: a big-number count-up, ranked bars, a percent ring or a line.

One clock: the visual starts at VISUAL_S, under the headline, so the first second already
shows the number counting, the ring filling or the bars growing; then its context, the
takeaway with the source line, and a hold of at least 4 s whose last 2 s are the end card
(15 s at least overall). The big number extrudes toward the viewer when its count-up lands,
the ring tilts up from flat, and bars grow with a lit top and end face. The optional headline
icon sits above the number, inside the ring, or beside the unit. With narration the visual
keeps its own clock; `pace` only delays the takeaway and the hold until the spoken headline
and body have finished.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from src.media.svg.reel_svg_charts import VISUAL_S, badge, bars, line
from src.media.svg.reel_svg_count import counter
from src.media.svg.svg_kit import (
    ASCENT,
    LEFT,
    MIN_S,
    RIGHT,
    RISE,
    SAFE,
    SWING,
    TRAVEL,
    Canvas,
    LayoutError,
    block_height,
    fit,
    fmt,
    text_width,
)
from src.media.svg.svg_parts import SOURCE_H, header, icon, source, takeaway, takeaway_height
from src.media.svg.svg_solid import extruded, extrusion_room

HEAD_S, COUNT_S, TAKE_S = 2.0, 2.4, 1.3
CONTEXT_PX, CHART_PX = (38, 34), 34  # context line, unit
BIG_ICON = 120


def _context(canvas: Canvas, top: float, text: str, start: float) -> tuple[str, float]:
    size, lines = fit(text, CONTEXT_PX, RIGHT - LEFT, 3)
    texts, bottom = canvas.lines(LEFT, top, lines, size, canvas.look.muted)
    return canvas.reveal(texts, start), bottom


def _context_height(text: str) -> float:
    size, lines = fit(text, CONTEXT_PX, RIGHT - LEFT, 3)
    return block_height(len(lines), size)


def _big_number(canvas: Canvas, scene: dict[str, Any], top: float, bottom: float) -> list[str]:
    value, name = scene["value"], scene.get("icon")
    unit_h = 64 if scene.get("unit") else 0
    icon_h = 2 * 0.56 * BIG_ICON + 28 if name else 0
    fixed = 40 + unit_h + icon_h + _context_height(scene["context"])
    room = RIGHT - LEFT - 2 * extrusion_room()  # the face stays centred; its depth goes right
    size = min(240.0, room / text_width(value, 1, bold=True), (bottom - top - fixed) / 1.05)
    if size < 120:
        raise LayoutError("the stat value or context is too long to show large; shorten it")
    top += (bottom - top - fixed - 1.05 * size) / 2
    out = []
    if name:
        out.append(badge(canvas, name, 540, top + 0.56 * BIG_ICON, BIG_ICON, VISUAL_S - 0.2))
        top += icon_h
    baseline = top + 0.8 * size
    out.append(extruded(canvas, 540, baseline, value, size, VISUAL_S + COUNT_S))
    out.append(counter(canvas, (540, baseline), value, size, (VISUAL_S, COUNT_S)))
    y = baseline + 0.25 * size + 40
    if unit_h:
        look = canvas.look
        unit = canvas.text(
            540,
            y + ASCENT * CHART_PX,
            scene["unit"],
            CHART_PX,
            look.accent_text,
            bold=True,
            anchor="middle",
        )
        out.append(canvas.reveal([unit], VISUAL_S + COUNT_S))
        y += unit_h
    context, _ = _context(canvas, y, scene["context"], VISUAL_S + COUNT_S + 0.2)
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
        f'<circle cx="540" cy="{fmt(cy + 14)}" r="{fmt(radius)}" fill="none" stroke="{look.track}" '
        'stroke-width="44" stroke-opacity="0.3"/>'  # the ring's edge, so it reads as solid
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{look.track}" '
        'stroke-width="44" stroke-opacity="0.45"/>'
    )
    arc = (
        f'<circle cx="540" cy="{fmt(cy)}" r="{fmt(radius)}" fill="none" stroke="{look.accent}" '
        f'stroke-width="44" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}" transform="rotate(-90 540 {fmt(cy)})">'
        + canvas.anim(
            "stroke-dashoffset", [(VISUAL_S, dash), (VISUAL_S + COUNT_S, rest)], ease=TRAVEL
        )
        + "</circle>"
    )
    tilt = [(VISUAL_S, "1 0.2"), (VISUAL_S + 0.9, "1 1")]  # rises from lying flat
    ring = canvas.scaled(540, cy, tilt, track + arc, ease=SWING)
    inner = min(130.0, (2 * radius - 120) / text_width(scene["value"], 1, bold=True))
    count = counter(canvas, (540, cy + 0.36 * inner), scene["value"], inner, (VISUAL_S, COUNT_S))
    out = [ring, count]
    room = radius - 22 - 0.44 * inner - 28  # ring interior above the count-up
    if (name := scene.get("icon")) and room >= 48:
        size = min(80.0, room)
        badge_y = cy - 0.44 * inner - 14 - size / 2
        body = icon(name, 540 - size / 2, badge_y - size / 2, size, look.accent)
        out.append(canvas.reveal([body], VISUAL_S))
    context, _ = _context(canvas, cy + radius + 56, scene["context"], VISUAL_S + COUNT_S + 0.2)
    return [*out, context]


VARIANTS = {"big_number": _big_number, "ring": _ring, "bars": bars, "line": line}


def reveal_seconds(scene: dict[str, Any]) -> float:
    if scene["variant"] == "bars":
        return 0.55 * (len(scene["bars"]) - 1) + 0.6 + 0.8
    if scene["variant"] == "line":
        return 3.0 + 0.8
    return COUNT_S + 2.4


def timing(scene: dict[str, Any], pace: Sequence[float] = ()) -> tuple[float, float, float]:
    """When the spoken body starts, when the takeaway appears and when the hold starts.
    `pace` holds the seconds narration needs for the headline, the body and the takeaway."""
    head, body, take = pace or (0.0, 0.0, 0.0)
    body_at = max(HEAD_S, head)
    take_at = max(VISUAL_S + reveal_seconds(scene), body_at + body)
    return body_at, take_at, take_at + max(TAKE_S, take)


def beats(scene: dict[str, Any], pace: Sequence[float] = ()) -> list[float]:
    """When each narration line starts: the headline, the body, the takeaway."""
    body_at, take_at, _ = timing(scene, pace)
    return [0.0, body_at, take_at]


def duration(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    return max(MIN_S, round(timing(scene, pace)[2] + 5.5 - TAKE_S, 1))


def hold_start(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    """When the takeaway and source line have finished appearing."""
    return timing(scene, pace)[2]


def compose(
    canvas: Canvas,
    scene: dict[str, Any],
    source_line: str | None,
    *,
    kicker: bool = True,
    pace: Sequence[float] = (),
) -> list[str]:
    look = canvas.look
    parts, top = header(canvas, look.kicker("stat") if kicker else None, scene["headline"])
    source_h = SOURCE_H if source_line else 0
    take_h = takeaway_height(scene["takeaway"])
    limit = SAFE[3] - RISE
    take_top = limit - source_h - take_h
    visual = VARIANTS[scene["variant"]](canvas, scene, top + 48, take_top - 40)
    take_at = timing(scene, pace)[1]
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at)
    parts += [*visual, card]
    if source_line:
        parts.append(source(canvas, card_bottom, source_line, take_at + 0.3))
    return parts
