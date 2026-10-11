"""How-it-works layout: a vertical stack of step cards joined by connectors and packets.

One clock: hook 0-2.5 s, 2.2 s per step, the takeaway, then a 3 s hold. When every card
cannot stay expanded inside the safe area, a finished step collapses to its label so the
stack still fits, and the final frame shows the whole path of labels plus the takeaway.
"""

from __future__ import annotations

from typing import Any

from src.media.svg_kit import (
    ACCENT,
    CARD,
    INK,
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
    fit,
    fmt,
    header,
    takeaway,
    takeaway_height,
    wrap,
)

HOOK_S, STEP_S, TAKE_S, HOLD_S = 2.5, 2.2, 1.3, 3.0
COLLAPSED, DETAIL_TOP, DETAIL_SIZE = 84, 84, 40
GAPS = (54, 48, 42, 36, 30)
BADGE_X, BADGE_Y, BADGE_R, TEXT_X = LEFT + 52, 42, 26, LEFT + 104
TEXT_W = RIGHT - 32 - TEXT_X


def duration(scene: dict[str, Any]) -> float:
    return round(HOOK_S + STEP_S * len(scene["steps"]) + TAKE_S + HOLD_S, 2)


def _plan(
    top: float, heights: list[float], take_h: float
) -> tuple[list[float], float, bool] | None:
    """Card tops, gap and collapse mode: expanded if possible, then the widest gap that fits."""
    limit = SAFE[3] - RISE
    for collapse in (False, True):
        for gap in GAPS:
            tops, y = [], top
            for height in heights:
                tops.append(y)
                y += (COLLAPSED if collapse else height) + gap
            phases = all(t + h <= limit for t, h in zip(tops, heights, strict=True))
            if phases and y + take_h <= limit:
                return tops, gap, collapse
    return None


def compose(canvas: Canvas, scene: dict[str, Any], *, kicker: bool = True) -> list[str]:
    parts, bottom = header(canvas, "HOW IT WORKS" if kicker else None, scene["hook"])
    steps = scene["steps"]
    size = (
        DETAIL_SIZE if all(len(wrap(s["detail"], DETAIL_SIZE, TEXT_W)) <= 3 for s in steps) else 36
    )
    details = [wrap(step["detail"], size, TEXT_W) for step in steps]
    if any(len(lines) > 3 for lines in details):
        raise LayoutError("a step detail needs more than three lines; shorten it")
    heights = [DETAIL_TOP + block_height(len(lines), size) + 24 for lines in details]
    take_h = takeaway_height(scene["takeaway"])
    plan = _plan(bottom + 44, heights, take_h)
    if plan is None:
        raise LayoutError("the steps do not fit; use fewer or shorter steps")
    tops, gap, collapse = plan
    begin = [HOOK_S + STEP_S * i for i in range(len(steps))]
    take_at = HOOK_S + STEP_S * len(steps)
    ends = [*begin[1:], take_at]
    cards, wires = [], []
    for i, step in enumerate(steps):
        appear = begin[i] + (0.15 if i == 0 else 0.55)
        shape = (tops[i], heights[i], details[i], size)
        cards.append(_card(canvas, step, i, shape, (appear, ends[i]), collapse))
        if i:
            y0 = tops[i - 1] + BADGE_Y + BADGE_R + 6
            wires.append(_wire(canvas, y0, tops[i] + BADGE_Y - BADGE_R - 6, begin[i] + 0.25))
    last = tops[-1] + (COLLAPSED if collapse else heights[-1])
    card, _ = takeaway(canvas, last + gap, scene["takeaway"], take_at + 0.35)
    return [*parts, *cards, *wires, card]


def _card(
    canvas: Canvas,
    step: dict[str, Any],
    index: int,
    shape: tuple[float, float, list[str], float],
    window: tuple[float, float],
    collapse: bool,
) -> str:
    top, height, detail, detail_size = shape
    appear, done = window
    rect = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{fmt(height)}" '
        f'rx="28" fill="{CARD}" stroke="{ACCENT}" stroke-width="4" stroke-opacity="0">'
    )
    rect += canvas.anim(
        "stroke-opacity", [(appear, "0"), (appear + 0.3, "1"), (done, "1"), (done + 0.3, "0")]
    )
    if collapse:
        rect += canvas.anim("height", [(done, fmt(height)), (done + 0.35, str(COLLAPSED))])
    rect += "</rect>"
    cy = top + BADGE_Y
    badge = f'<circle cx="{BADGE_X}" cy="{fmt(cy)}" r="{BADGE_R}" fill="{ACCENT}"/>'
    number = canvas.text(BADGE_X, cy + 12, str(index + 1), 34, INK, bold=True, anchor="middle")
    size, label = fit(step["label"], (56, 52), TEXT_W, 1, bold=True)
    title = canvas.text(TEXT_X, cy + 0.36 * size, label[0], size, TEXT, bold=True)
    lines, _ = canvas.lines(TEXT_X, top + DETAIL_TOP, detail, detail_size, MUTED)
    fade = canvas.fade(appear + 0.2, done if collapse else None)
    body = f'<g opacity="0">{fade}{"".join(lines)}</g>'
    return canvas.reveal([rect, badge, number, title, body], appear)


def _wire(canvas: Canvas, y0: float, y1: float, start: float) -> str:
    """Connector that draws down to the next badge, with a packet riding it."""
    dash = fmt(max(y1 - y0, 1) + 2)
    line = (
        f'<line x1="{BADGE_X}" y1="{fmt(y0)}" x2="{BADGE_X}" y2="{fmt(y1)}" stroke="{ACCENT}" '
        f'stroke-width="6" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}">'
        + canvas.anim("stroke-dashoffset", [(start, dash), (start + 0.4, "0")])
        + "</line>"
    )
    times = ";".join(canvas.key(t) for t in (0, start + 0.05, start + 0.5, canvas.total))
    glow = [(start + 0.05, "0"), (start + 0.1, "1"), (start + 0.5, "1"), (start + 0.6, "0")]
    packet = (
        f'<circle r="11" fill="{PACKET}" opacity="0">'
        f'<animateMotion path="M{BADGE_X} {fmt(y0)} V{fmt(y1)}" dur="{fmt(canvas.total)}s" '
        f'fill="freeze" calcMode="linear" keyPoints="0;0;1;1" keyTimes="{times}"/>'
        + canvas.anim("opacity", glow)
        + "</circle>"
    )
    return line + packet
