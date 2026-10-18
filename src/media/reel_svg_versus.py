"""Two things compared row by row: "TCP vs UDP" with 3 or 4 aspects side by side.

One clock: hook 0-2.5 s (the two column heads arrive during it), 2.6 s per row, the takeaway,
then a 4 s hold whose last 2 s are the end card. Each row lights up while it is active, its
right-hand cell arriving when a narrator would reach it, then dims until the takeaway, so the
final frame is the whole table plus the takeaway. With narration, `pace` lengthens any beat
its spoken line needs (never shortens).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.media.svg_kit import (
    ASCENT,
    DETAIL_PX,
    LABEL_PX,
    LEFT,
    RIGHT,
    RISE,
    SAFE,
    Canvas,
    LayoutError,
    block_height,
    fit,
    fmt,
    leading,
    text_width,
    wrap,
)
from src.media.svg_parts import ghost, header, icon, takeaway, takeaway_height, tile

HOOK_S, ROW_S, TAKE_S, HOLD_S = 2.5, 2.6, 1.3, 4.0
GAP = 20
ASPECT_W = 284  # fits a 13-letter aspect word such as "Compatibility" in bold
CELL_W = (RIGHT - LEFT - ASPECT_W - 2 * GAP) // 2  # 306 px per compared thing
CELL_X = (LEFT + ASPECT_W + GAP, LEFT + ASPECT_W + 2 * GAP + CELL_W)
# Names step down to 36 px so one long word ("Microservices") still fits its column.
TEXT_PX, NAME_PX, ICON_PX, PAD = DETAIL_PX[-1], (*LABEL_PX, 40, 36), 96, 16


def timing(scene: dict[str, Any], pace: Sequence[float] = ()) -> tuple[list[float], float, float]:
    """Each row's start, the takeaway's and the hold's. `pace` holds the seconds narration
    needs for the hook, each row and the takeaway."""
    need = list(pace) or [0.0] * (len(scene["rows"]) + 2)
    at, begin = max(HOOK_S, need[0]), []
    for index in range(len(scene["rows"])):
        begin.append(at)
        at += max(ROW_S, need[1 + index])
    return begin, at, at + max(TAKE_S, need[-1])


def beats(scene: dict[str, Any], pace: Sequence[float] = ()) -> list[float]:
    """When each narration line's beat starts: the hook, each row, the takeaway."""
    begin, take_at, _ = timing(scene, pace)
    return [0.0, *begin, take_at]


def duration(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    return round(timing(scene, pace)[2] + HOLD_S, 2)


def hold_start(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    return duration(scene, pace) - HOLD_S


def _icon_space(scene: dict[str, Any]) -> float:
    """Room above both names when either side has an icon, so the names stay level."""
    return ICON_PX + 24 if any(scene[side].get("icon") for side in ("left", "right")) else 0


def _head(
    canvas: Canvas, side: dict[str, Any], x: float, top: float, at: float, space: float
) -> str:
    """One compared thing: its icon (when it has one) above its name, centred on its cell."""
    look, cx = canvas.look, x + CELL_W / 2
    parts, y = [], top
    if name := side.get("icon"):
        radius = ICON_PX / 2 + 6
        parts.append(tile(canvas, cx, y + radius, radius))
        parts.append(icon(name, cx - ICON_PX / 2, y + 6, ICON_PX, look.accent))
    y += space
    size, lines = fit(side["name"], NAME_PX, CELL_W, 2, bold=True)
    for row, line in enumerate(lines):
        baseline = y + ASCENT * size + row * leading(size)
        parts.append(canvas.text(cx, baseline, line, size, look.text, bold=True, anchor="middle"))
    return canvas.reveal(parts, at)


def _head_height(scene: dict[str, Any]) -> float:
    names = [fit(scene[side]["name"], NAME_PX, CELL_W, 2, bold=True) for side in ("left", "right")]
    return _icon_space(scene) + max(block_height(len(lines), size) for size, lines in names)


def _words_fit(text: str, size: float, width: float, *, bold: bool) -> None:
    """A word wider than its column would be split mid-word; ask for a shorter one instead."""
    if any(text_width(word, size, bold=bold) > width for word in text.split()):
        raise LayoutError(f'"{text}" has a word too long for its column; use a shorter word')


def _rows(scene: dict[str, Any]) -> list[tuple[list[str], list[str], list[str], float]]:
    """Each row's wrapped aspect, left and right text and its card height."""
    out = []
    for row in scene["rows"]:
        _words_fit(row["aspect"], TEXT_PX, ASPECT_W - 2 * PAD, bold=True)
        for cell in (row["left"], row["right"]):
            _words_fit(cell, TEXT_PX, CELL_W - PAD, bold=False)
        aspect = wrap(row["aspect"], TEXT_PX, ASPECT_W - 2 * PAD, bold=True)
        left = wrap(row["left"], TEXT_PX, CELL_W - PAD)
        right = wrap(row["right"], TEXT_PX, CELL_W - PAD)
        if max(len(aspect), len(left), len(right)) > 3:
            raise LayoutError("a versus row needs more than three lines; shorten it")
        lines = max(len(aspect), len(left), len(right))
        out.append((aspect, left, right, block_height(lines, TEXT_PX) + 2 * PAD))
    return out


def compose(
    canvas: Canvas,
    scene: dict[str, Any],
    *,
    kicker: bool = True,
    pace: Sequence[float] = (),
) -> list[str]:
    look = canvas.look
    parts, bottom = header(canvas, look.kicker("versus") if kicker else None, scene["hook"])
    heads_top = bottom + 32
    rows = _rows(scene)
    take_h = takeaway_height(scene["takeaway"])
    top = heads_top + _head_height(scene) + 24
    take_top = top + sum(h for *_, h in rows) + 12 * (len(rows) - 1) + 24
    if take_top + take_h > SAFE[3] - RISE:
        raise LayoutError("the comparison does not fit; shorten the hook, cells or takeaway")
    for side in ("left", "right"):
        _words_fit(scene[side]["name"], NAME_PX[-1], CELL_W, bold=True)
    begin, take_at, _ = timing(scene, pace)
    space = _icon_space(scene)
    divider = (  # behind the row cards, so it only shows in the gaps between them
        f'<rect x="{fmt(CELL_X[1] - GAP / 2 - 2)}" y="{fmt(heads_top)}" width="4" '
        f'height="{fmt(take_top - 24 - heads_top)}" rx="2" fill="{look.accent}" opacity="0">'
        f"{canvas.fade(1.6)}</rect>"
    )
    parts.append(divider)
    parts.append(_head(canvas, scene["left"], CELL_X[0], heads_top, 0.9, space))
    parts.append(_head(canvas, scene["right"], CELL_X[1], heads_top, 1.3, space))
    ends = [*begin[1:], take_at]
    for index, (aspect, left, right, height) in enumerate(rows):
        start, done = begin[index] + 0.15, ends[index]
        right_at = start + 0.45 * (done - begin[index])
        parts.append(ghost(canvas, LEFT, top, RIGHT - LEFT, height))
        parts.append(
            _row(canvas, (top, height), (aspect, left, right), (start, right_at, done, take_at))
        )
        top += height + 12
    card, _ = takeaway(canvas, take_top, scene["takeaway"], take_at + 0.35)
    return [*parts, card]


def _row(
    canvas: Canvas,
    place: tuple[float, float],
    texts: tuple[list[str], list[str], list[str]],
    window: tuple[float, float, float, float],
) -> str:
    """A row card: the aspect, then the left cell, then the right one; it glows while active."""
    look = canvas.look
    top, height = place
    aspect, left, right = texts
    start, right_at, done, undim = window
    lit = [(start, "0"), (start + 0.3, "1"), (done, "1"), (done + 0.3, "0")]
    card = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{fmt(height)}" rx="24" '
        f'fill="{look.card}" stroke="{look.accent}" stroke-width="4" stroke-opacity="0">'
        + canvas.anim("stroke-opacity", lit)
        + "</rect>"
    )
    name, _ = canvas.lines(LEFT + PAD, top + PAD, aspect, TEXT_PX, look.accent_text, bold=True)
    first, _ = canvas.lines(CELL_X[0], top + PAD, left, TEXT_PX, look.text)
    second, _ = canvas.lines(CELL_X[1], top + PAD, right, TEXT_PX, look.text)
    other = f'<g opacity="0">{canvas.fade(right_at)}{"".join(second)}</g>'
    return canvas.reveal([card, *name, *first, other], start, dim=(done, undim))
