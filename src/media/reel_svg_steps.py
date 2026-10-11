"""How-it-works layout: a chain of icon rows joined by connectors, with a packet riding each.

One clock: hook 0-2.5 s, 2.2 s per step, the takeaway, then a 4 s hold whose last 2 s are
the end card. The icon and the connector carry each beat: a step's one-line detail shows only
while it is active (its card glows and its icon pops), then the row collapses to icon and
label and dims until the takeaway, so the final frame is the whole path plus the takeaway.
"""

from __future__ import annotations

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
    wrap,
)
from src.media.svg_parts import header, icon, takeaway, takeaway_height, tile

HOOK_S, STEP_S, TAKE_S, HOLD_S = 2.5, 2.2, 1.3, 4.0
# Icon px, row padding and gap between rows: the roomiest that fits is used.
SIZES = ((128, 16, 28), (120, 14, 24), (112, 12, 20), (104, 10, 16), (96, 8, 14), (96, 6, 10))
DETAIL_SIZES = (40, 36)
NUMBER_W = 96  # right-hand room for the step number


def duration(scene: dict[str, Any]) -> float:
    return round(HOOK_S + STEP_S * len(scene["steps"]) + TAKE_S + HOLD_S, 2)


def hold_start(scene: dict[str, Any]) -> float:
    return duration(scene) - HOLD_S


class _Rows:
    """Geometry of one icon size: tile, text column, collapsed and expanded heights."""

    def __init__(self, size: int, pad: int, gap: int, details: list[list[str]], px: float):
        self.size, self.pad, self.gap = size, pad, gap
        self.radius = size / 2 + 6
        self.row = 2 * self.radius + 2 * pad
        self.cx = LEFT + 20 + self.radius
        self.text_x = self.cx + self.radius + 28
        self.detail_px = px
        self.label_top = self.row / 2 + 0.36 * 56 + 0.25 * 56 + 14  # detail top, from row top
        self.open = [self.label_top + block_height(len(lines), px) + 22 for lines in details]

    def tops(self, top: float, take_h: float) -> list[float] | None:
        limit = SAFE[3] - RISE
        tops = [top + i * (self.row + self.gap) for i in range(len(self.open))]
        expanded = all(t + h <= limit for t, h in zip(tops, self.open, strict=True))
        if expanded and tops[-1] + self.row + self.gap + take_h <= limit:
            return tops
        return None


def _layout(scene: dict[str, Any], top: float) -> tuple[_Rows, list[float], list[list[str]]]:
    steps = scene["steps"]
    take_h = takeaway_height(scene["takeaway"])
    for size, pad, gap in SIZES:
        text_w = RIGHT - 28 - (LEFT + 20 + size + 12 + 28)
        for px in DETAIL_SIZES:
            details = [wrap(step["detail"], px, text_w) for step in steps]
            if all(len(lines) <= 2 for lines in details):
                break
        if any(len(lines) > 3 for lines in details):
            raise LayoutError("a step detail needs more than three lines; shorten it")
        rows = _Rows(size, pad, gap, details, px)
        if (tops := rows.tops(top, take_h)) is not None:
            return rows, tops, details
    raise LayoutError("the steps do not fit; shorten the hook or takeaway, or use fewer steps")


def compose(canvas: Canvas, scene: dict[str, Any], *, kicker: bool = True) -> list[str]:
    look = canvas.look
    parts, bottom = header(canvas, look.kicker("steps") if kicker else None, scene["hook"])
    steps = scene["steps"]
    rows, tops, details = _layout(scene, bottom + 32)
    begin = [HOOK_S + STEP_S * i for i in range(len(steps))]
    take_at = HOOK_S + STEP_S * len(steps)
    ends = [*begin[1:], take_at]
    cards, wires = [], []
    for i, step in enumerate(steps):
        appear = begin[i] + (0.15 if i == 0 else 0.55)
        cards.append(
            _card(canvas, rows, step, i, (tops[i], details[i]), (appear, ends[i], take_at))
        )
        if i:
            y0 = tops[i - 1] + rows.row / 2 + rows.radius + 6
            wires.append(
                _wire(canvas, rows.cx, y0, tops[i] + rows.row / 2 - rows.radius - 6, begin[i])
            )
    take_top = tops[-1] + rows.row + rows.gap
    card, _ = takeaway(canvas, take_top, scene["takeaway"], take_at + 0.35)
    return [*parts, *cards, *wires, card]


def _card(
    canvas: Canvas,
    rows: _Rows,
    step: dict[str, Any],
    index: int,
    place: tuple[float, list[str]],
    window: tuple[float, float, float],
) -> str:
    look = canvas.look
    top, detail = place
    appear, done, undim = window
    height = rows.open[index]
    width = RIGHT - LEFT
    lit = [(appear, "0"), (appear + 0.3, "0.28"), (done, "0.28"), (done + 0.3, "0")]
    glow = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{width}" height="{fmt(height)}" rx="28" '
        f'fill="none" stroke="{look.accent}" stroke-width="16" stroke-opacity="0">'
        + canvas.anim("stroke-opacity", lit)
        + canvas.anim("height", [(done, fmt(height)), (done + 0.35, fmt(rows.row))])
        + "</rect>"
    )
    rect = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{width}" height="{fmt(height)}" rx="28" '
        f'fill="{look.card}" stroke="{look.accent}" stroke-width="4" stroke-opacity="0">'
        + canvas.anim(
            "stroke-opacity", [(appear, "0"), (appear + 0.3, "1"), (done, "1"), (done + 0.3, "0")]
        )
        + canvas.anim("height", [(done, fmt(height)), (done + 0.35, fmt(rows.row))])
        + "</rect>"
    )
    cy = top + rows.row / 2
    mark = _mark(canvas, rows, step, index, cy)
    pop = [(appear + 0.1, "1"), (appear + 0.4, "1.14"), (done, "1.14"), (done + 0.35, "1")]
    mark = canvas.scaled(rows.cx, cy, pop, mark)
    size, label = fit(step["label"], (56, 52), RIGHT - NUMBER_W - rows.text_x, 1, bold=True)
    title = canvas.text(rows.text_x, cy + 0.36 * size, label[0], size, look.text, bold=True)
    if step.get("icon"):  # the order, in the corner the label leaves free
        digit = str(index + 1)
        title += canvas.text(
            RIGHT - 36, cy + 0.36 * 44, digit, 44, look.accent_text, bold=True, anchor="end"
        )
    lines, _ = canvas.lines(rows.text_x, top + rows.label_top, detail, rows.detail_px, look.muted)
    body = f'<g opacity="0">{canvas.fade(appear + 0.2, done)}{"".join(lines)}</g>'
    return canvas.reveal([glow, rect, mark, title, body], appear, dim=(done, undim))


def _mark(canvas: Canvas, rows: _Rows, step: dict[str, Any], index: int, cy: float) -> str:
    """The step's icon on its tile, or its number on the tile when it has no icon."""
    look = canvas.look
    shape = tile(canvas, rows.cx, cy, rows.radius)
    if name := step.get("icon"):
        half = rows.size / 2
        return shape + icon(name, rows.cx - half, cy - half, rows.size, look.accent)
    digit = str(index + 1)
    return shape + canvas.text(
        rows.cx, cy + 0.36 * 64, digit, 64, look.accent_text, bold=True, anchor="middle"
    )


def _wire(canvas: Canvas, x: float, y0: float, y1: float, start: float) -> str:
    """Connector that draws down to the next icon, with a packet riding it."""
    look = canvas.look
    start += 0.25
    dash = fmt(max(y1 - y0, 1) + 2)
    line = (
        f'<line x1="{fmt(x)}" y1="{fmt(y0)}" x2="{fmt(x)}" y2="{fmt(y1)}" stroke="{look.accent}" '
        f'stroke-width="8" stroke-linecap="round" stroke-dasharray="{dash}" '
        f'stroke-dashoffset="{dash}">'
        + canvas.anim("stroke-dashoffset", [(start, dash), (start + 0.4, "0")])
        + "</line>"
    )
    times = ";".join(canvas.key(t) for t in (0, start + 0.05, start + 0.5, canvas.total))
    glow = [(start + 0.05, "0"), (start + 0.1, "1"), (start + 0.5, "1"), (start + 0.6, "0")]
    packet = (
        f'<circle r="13" fill="{look.packet}" opacity="0">'
        f'<animateMotion path="M{fmt(x)} {fmt(y0)} V{fmt(y1)}" dur="{fmt(canvas.total)}s" '
        f'fill="freeze" calcMode="linear" keyPoints="0;0;1;1" keyTimes="{times}"/>'
        + canvas.anim("opacity", glow)
        + "</circle>"
    )
    return line + packet
