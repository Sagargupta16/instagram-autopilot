"""The story of X: 4 to 6 dated milestones that reveal in turn down a rail.

One clock: hook 0-2.5 s, 2.2 s per milestone, the takeaway with its source line, then a 3 s
hold. Dates sit beside their event when they are short and above it when they are not.
"""

from __future__ import annotations

from typing import Any

from src.media.svg_kit import (
    ACCENT,
    ACCENT_TEXT,
    LEFT,
    MUTED,
    PACKET,
    RIGHT,
    RISE,
    SAFE,
    TEXT,
    Canvas,
    LayoutError,
    block_height,
    fmt,
    header,
    takeaway,
    takeaway_height,
    text_width,
    wrap,
)

HOOK_S, ITEM_S, TAKE_S, HOLD_S = 2.5, 2.2, 1.3, 3.0
RAIL_X, DOT_R, DATE_X, GAP = LEFT + 24, 14, LEFT + 68, 34


def duration(scene: dict[str, Any]) -> float:
    return round(HOOK_S + ITEM_S * len(scene["milestones"]) + TAKE_S + HOLD_S, 2)


def _rows(milestones: list[dict[str, str]]) -> tuple[float, list[list[str]], bool]:
    """Event column x, wrapped events, and whether dates sit beside them."""
    date_w = max(text_width(item["date"], 44, bold=True) for item in milestones)
    beside = date_w <= 300
    event_x = DATE_X + date_w + 28 if beside else DATE_X
    events = [wrap(item["event"], 36, RIGHT - event_x) for item in milestones]
    if any(len(lines) > 3 for lines in events):
        raise LayoutError("a milestone event needs more than three lines; shorten it")
    return event_x, events, beside


def _row_height(lines: int, beside: bool) -> float:
    event = block_height(lines, 36) + (0.8 * 44 - 0.8 * 36 if beside else 0.8 * 44 + 0.25 * 44 + 10)
    return max(1.05 * 44, event)


def compose(
    canvas: Canvas, scene: dict[str, Any], source_line: str | None, *, kicker: bool = True
) -> list[str]:
    parts, top = header(canvas, "TIMELINE" if kicker else None, scene["hook"])
    milestones = scene["milestones"]
    event_x, events, beside = _rows(milestones)
    heights = [_row_height(len(lines), beside) for lines in events]
    source_h = 38 + 28 if source_line else 0
    take_top = SAFE[3] - RISE - source_h - takeaway_height(scene["takeaway"])
    y = top + 52
    if y + sum(heights) + GAP * (len(heights) - 1) > take_top - 40:
        raise LayoutError("the milestones do not fit; use fewer or shorter milestones")
    rows, rails, prev_dot = [], [], None
    for i, (item, lines) in enumerate(zip(milestones, events, strict=True)):
        start = HOOK_S + ITEM_S * i
        appear = start + (0.15 if i == 0 else 0.45)
        baseline = y + 0.8 * 44
        dot_y = baseline - 0.36 * 44
        texts = [canvas.text(DATE_X, baseline, item["date"], 44, ACCENT_TEXT, bold=True)]
        event_top = baseline - 0.8 * 36 if beside else baseline + 0.25 * 44 + 10
        more, _ = canvas.lines(event_x, event_top, lines, 36, TEXT)
        dot = (
            f'<circle cx="{RAIL_X}" cy="{fmt(dot_y)}" r="{DOT_R}" fill="{ACCENT}">'
            + canvas.anim("r", [(appear, "0"), (appear + 0.3, str(DOT_R))])
            + "</circle>"
        )
        rows += [dot, canvas.reveal([*texts, *more], appear)]
        if prev_dot is not None:
            rails.append(_rail(canvas, prev_dot + DOT_R + 6, dot_y - DOT_R - 6, start))
        prev_dot = dot_y
        y += heights[i] + GAP
    take_at = HOOK_S + ITEM_S * len(milestones)
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at + 0.1)
    parts += [*rails, *rows, card]
    if source_line:
        line = canvas.text(LEFT, card_bottom + 28 + 29, source_line, 36, MUTED)
        parts.append(canvas.reveal([line], take_at + 0.4))
    return parts


def _rail(canvas: Canvas, y0: float, y1: float, start: float) -> str:
    dash = fmt(max(y1 - y0, 1) + 2)
    line = (
        f'<line x1="{RAIL_X}" y1="{fmt(y0)}" x2="{RAIL_X}" y2="{fmt(y1)}" stroke="{ACCENT}" '
        f'stroke-width="6" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}">'
        + canvas.anim("stroke-dashoffset", [(start, dash), (start + 0.5, "0")])
        + "</line>"
    )
    times = ";".join(canvas.key(t) for t in (0, start + 0.05, start + 0.55, canvas.total))
    glow = [(start + 0.05, "0"), (start + 0.1, "1"), (start + 0.55, "1"), (start + 0.65, "0")]
    packet = (
        f'<circle r="10" fill="{PACKET}" opacity="0">'
        f'<animateMotion path="M{RAIL_X} {fmt(y0)} V{fmt(y1)}" dur="{fmt(canvas.total)}s" '
        f'fill="freeze" calcMode="linear" keyPoints="0;0;1;1" keyTimes="{times}"/>'
        + canvas.anim("opacity", glow)
        + "</circle>"
    )
    return line + packet
