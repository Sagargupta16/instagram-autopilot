"""The story of X: 4 to 6 dated milestones that reveal in turn down a rail of icon nodes.

One clock: hook 0-2.5 s, 2.2 s per milestone, the takeaway with its source line, then a 4 s
hold whose last 2 s are the end card. The active milestone's node pops and glows while the
earlier ones dim; every row is back at full strength for the takeaway and the hold. Dates sit
beside their event when they are short and above it when they are not.
"""

from __future__ import annotations

from typing import Any

from src.media.svg_kit import (
    ASCENT,
    LEFT,
    RIGHT,
    RISE,
    SAFE,
    Canvas,
    LayoutError,
    block_height,
    fmt,
    leading,
    text_width,
    wrap,
)
from src.media.svg_parts import header, icon, takeaway, takeaway_height, tile

HOOK_S, ITEM_S, TAKE_S, HOLD_S = 2.5, 2.2, 1.3, 4.0
DATE_PX, EVENT_PX = 44, 36
# Node radius, icon px and gap between rows: the roomiest that fits is used.
SIZES = ((52, 76, 24), (48, 70, 18), (44, 64, 14), (40, 58, 10))


def duration(scene: dict[str, Any]) -> float:
    return round(HOOK_S + ITEM_S * len(scene["milestones"]) + TAKE_S + HOLD_S, 2)


def hold_start(scene: dict[str, Any]) -> float:
    return duration(scene) - HOLD_S


def _text_block(lines: int, beside: bool) -> float:
    """Height of a row's date and event text."""
    if beside:
        return block_height(lines, EVENT_PX) + (ASCENT * DATE_PX - ASCENT * EVENT_PX)
    return 1.05 * DATE_PX + 10 + block_height(lines, EVENT_PX)


def _rows(milestones: list[dict[str, str]], date_x: float) -> tuple[float, list[list[str]], bool]:
    """Event column x, wrapped events, and whether dates sit beside them."""
    date_w = max(text_width(item["date"], DATE_PX, bold=True) for item in milestones)
    beside = date_w <= 300
    event_x = date_x + date_w + 28 if beside else date_x
    events = [wrap(item["event"], EVENT_PX, RIGHT - event_x) for item in milestones]
    if any(len(lines) > 3 for lines in events):
        raise LayoutError("a milestone event needs more than three lines; shorten it")
    return event_x, events, beside


def _size(milestones: list[dict[str, str]], room: float) -> tuple[int, int, int]:
    """The roomiest node radius, icon size and gap whose rows fit `room`."""
    for radius, size, gap in SIZES:
        _, events, beside = _rows(milestones, LEFT + 20 + 2 * radius + 28)
        heights = [max(2 * radius, _text_block(len(lines), beside)) for lines in events]
        if sum(heights) + gap * (len(heights) - 1) <= room:
            return radius, size, gap
    raise LayoutError("the milestones do not fit; use fewer or shorter milestones")


def compose(
    canvas: Canvas, scene: dict[str, Any], source_line: str | None, *, kicker: bool = True
) -> list[str]:
    look = canvas.look
    parts, top = header(canvas, look.kicker("timeline") if kicker else None, scene["hook"])
    milestones = scene["milestones"]
    source_h = 38 + 28 if source_line else 0
    take_top = SAFE[3] - RISE - source_h - takeaway_height(scene["takeaway"])
    radius, size, gap = _size(milestones, take_top - 40 - (top + 44))
    rail_x = LEFT + 20 + radius
    event_x, events, beside = _rows(milestones, rail_x + radius + 28)
    heights = [max(2 * radius, _text_block(len(lines), beside)) for lines in events]
    take_at = HOOK_S + ITEM_S * len(milestones)
    y, rows, rails, prev = top + 44, [], [], None
    for i, (item, lines) in enumerate(zip(milestones, events, strict=True)):
        start = HOOK_S + ITEM_S * i
        appear = start + (0.15 if i == 0 else 0.45)
        done = start + ITEM_S if i < len(milestones) - 1 else take_at
        cy = y + heights[i] / 2
        block = _text_block(len(lines), beside)
        text_top = cy - block / 2
        node = _node(canvas, item, rail_x, cy, (radius, size), (appear, done, take_at))
        texts = _texts(canvas, item, lines, (rail_x + radius + 28, event_x, text_top), beside)
        rows += [node, canvas.reveal(texts, appear, dim=(done, take_at))]
        if prev is not None:
            rails.append(_rail(canvas, rail_x, prev + radius + 6, cy - radius - 6, start))
        prev = cy
        y += heights[i] + gap
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at + 0.1)
    parts += [*rails, *rows, card]
    if source_line:
        line = canvas.text(LEFT, card_bottom + 28 + 29, source_line, 36, look.muted)
        parts.append(canvas.reveal([line], take_at + 0.4))
    return parts


def _texts(
    canvas: Canvas,
    item: dict[str, str],
    lines: list[str],
    columns: tuple[float, float, float],
    beside: bool,
) -> list[str]:
    look = canvas.look
    date_x, event_x, top = columns
    baseline = top + ASCENT * DATE_PX
    texts = [canvas.text(date_x, baseline, item["date"], DATE_PX, look.accent_text, bold=True)]
    event_top = baseline - ASCENT * EVENT_PX if beside else top + 1.05 * DATE_PX + 10
    for j, line in enumerate(lines):
        y = event_top + ASCENT * EVENT_PX + j * leading(EVENT_PX)
        texts.append(canvas.text(event_x, y, line, EVENT_PX, look.text))
    return texts


def _node(
    canvas: Canvas,
    item: dict[str, str],
    x: float,
    cy: float,
    shape: tuple[float, float],
    window: tuple[float, float, float],
) -> str:
    """The milestone's icon on its tile (a dot without one), popping while it is active."""
    look = canvas.look
    radius, size = shape
    appear, done, undim = window
    ring = (
        f'<circle cx="{fmt(x)}" cy="{fmt(cy)}" r="{fmt(radius + 6)}" fill="none" '
        f'stroke="{look.accent}" stroke-width="12" stroke-opacity="0">'
        + canvas.anim(
            "stroke-opacity",
            [(appear, "0"), (appear + 0.3, "0.3"), (done, "0.3"), (done + 0.3, "0")],
        )
        + "</circle>"
    )
    body = tile(canvas, x, cy, radius)
    if name := item.get("icon"):
        body += icon(name, x - size / 2, cy - size / 2, size, look.accent)
    else:
        body += f'<circle cx="{fmt(x)}" cy="{fmt(cy)}" r="14" fill="{look.accent}"/>'
    pop = [(appear, "0"), (appear + 0.3, "1.15"), (done, "1.15"), (done + 0.3, "1")]
    dim = canvas.dimming(done, undim)
    shade = canvas.anim("opacity", dim) if dim else ""
    return ring + canvas.scaled(x, cy, pop, body, also=shade)


def _rail(canvas: Canvas, x: float, y0: float, y1: float, start: float) -> str:
    look = canvas.look
    dash = fmt(max(y1 - y0, 1) + 2)
    line = (
        f'<line x1="{fmt(x)}" y1="{fmt(y0)}" x2="{fmt(x)}" y2="{fmt(y1)}" stroke="{look.accent}" '
        f'stroke-width="8" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}">'
        + canvas.anim("stroke-dashoffset", [(start, dash), (start + 0.5, "0")])
        + "</line>"
    )
    times = ";".join(canvas.key(t) for t in (0, start + 0.05, start + 0.55, canvas.total))
    glow = [(start + 0.05, "0"), (start + 0.1, "1"), (start + 0.55, "1"), (start + 0.65, "0")]
    packet = (
        f'<circle r="12" fill="{look.packet}" opacity="0">'
        f'<animateMotion path="M{fmt(x)} {fmt(y0)} V{fmt(y1)}" dur="{fmt(canvas.total)}s" '
        f'fill="freeze" calcMode="linear" keyPoints="0;0;1;1" keyTimes="{times}"/>'
        + canvas.anim("opacity", glow)
        + "</circle>"
    )
    return line + packet
