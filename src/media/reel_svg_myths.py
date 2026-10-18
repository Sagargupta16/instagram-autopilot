"""Myth vs fact: 2 or 3 common beliefs, each struck through and replaced by what is true.

One clock: hook 0-2.5 s, then per item 1.6 s for the myth and 2.2 s for the fact, the
takeaway with its source line, then a 4 s hold whose last 2 s are the end card. A card shows
MYTH and the belief; on its fact beat a line strikes the belief and FACT appears beneath it.
Finished cards dim until the takeaway, so the final frame is every myth crossed out above its
fact. Narration speaks the myth and the fact as two lines, so `pace` (which only lengthens
beats) lines the strike up with the spoken word "Fact".
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.media.svg_kit import (
    ASCENT,
    DETAIL_PX,
    LEFT,
    RIGHT,
    RISE,
    SAFE,
    TRAVEL,
    Canvas,
    LayoutError,
    block_height,
    fmt,
    leading,
    text_width,
    wrap,
)
from src.media.svg_parts import SOURCE_H, header, source, takeaway, takeaway_height

HOOK_S, MYTH_S, FACT_S, TAKE_S, HOLD_S = 2.5, 1.6, 2.2, 1.3, 4.0
TEXT_PX, PAD, TAG_W, TAG_GAP = DETAIL_PX[-1], 20, 128, 14
TEXT_X = LEFT + PAD + TAG_W
TEXT_W = RIGHT - PAD - TEXT_X


def timing(
    scene: dict[str, Any], pace: Sequence[float] = ()
) -> tuple[list[float], list[float], float, float]:
    """Each myth's start, each fact's start, the takeaway's and the hold's. `pace` holds the
    seconds narration needs for the hook, each myth and fact in turn, and the takeaway."""
    count = len(scene["items"])
    need = list(pace) or [0.0] * (2 * count + 2)
    at, myths, facts = max(HOOK_S, need[0]), [], []
    for index in range(count):
        myths.append(at)
        at += max(MYTH_S, need[1 + 2 * index])
        facts.append(at)
        at += max(FACT_S, need[2 + 2 * index])
    return myths, facts, at, at + max(TAKE_S, need[-1])


def beats(scene: dict[str, Any], pace: Sequence[float] = ()) -> list[float]:
    """When each narration line starts: the hook, each myth and its fact, the takeaway."""
    myths, facts, take_at, _ = timing(scene, pace)
    return [0.0, *(at for pair in zip(myths, facts, strict=True) for at in pair), take_at]


def duration(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    return round(timing(scene, pace)[3] + HOLD_S, 2)


def hold_start(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    return duration(scene, pace) - HOLD_S


def _wrapped(scene: dict[str, Any]) -> list[tuple[list[str], list[str], float]]:
    """Each item's myth lines, fact lines and card height."""
    out = []
    for item in scene["items"]:
        myth, fact = wrap(item["myth"], TEXT_PX, TEXT_W), wrap(item["fact"], TEXT_PX, TEXT_W)
        if len(myth) > 2 or len(fact) > 3:
            raise LayoutError("a myth needs at most two lines and a fact three; shorten them")
        height = 2 * PAD + block_height(len(myth), TEXT_PX) + TAG_GAP
        out.append((myth, fact, height + block_height(len(fact), TEXT_PX)))
    return out


def compose(
    canvas: Canvas,
    scene: dict[str, Any],
    source_line: str | None,
    *,
    kicker: bool = True,
    pace: Sequence[float] = (),
) -> list[str]:
    look = canvas.look
    parts, bottom = header(canvas, look.kicker("myths") if kicker else None, scene["hook"])
    cards = _wrapped(scene)
    source_h = SOURCE_H if source_line else 0
    take_top = SAFE[3] - RISE - source_h - takeaway_height(scene["takeaway"])
    top = bottom + 32
    if top + sum(h for *_, h in cards) + 16 * (len(cards) - 1) + 24 > take_top:
        raise LayoutError("the myths do not fit; shorten the hook, myths, facts or takeaway")
    myths, facts, take_at, _ = timing(scene, pace)
    ends = [*myths[1:], take_at]
    for index, (myth, fact, height) in enumerate(cards):
        window = (myths[index] + 0.15, facts[index], ends[index], take_at)
        parts.append(_card(canvas, top, height, (myth, fact), window))
        top += height + 16
    card, card_bottom = takeaway(canvas, take_top, scene["takeaway"], take_at + 0.1)
    parts.append(card)
    if source_line:
        parts.append(source(canvas, card_bottom, source_line, take_at + 0.4))
    return parts


def _card(
    canvas: Canvas,
    top: float,
    height: float,
    texts: tuple[list[str], list[str]],
    window: tuple[float, float, float, float],
) -> str:
    """MYTH and the belief; at `fact_at` the belief is struck through and FACT arrives."""
    look = canvas.look
    myth, fact = texts
    appear, fact_at, done, undim = window
    lit = [(appear, "0"), (appear + 0.3, "1"), (done, "1"), (done + 0.3, "0")]
    rect = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{fmt(height)}" rx="24" '
        f'fill="{look.card}" stroke="{look.accent}" stroke-width="4" stroke-opacity="0">'
        + canvas.anim("stroke-opacity", lit)
        + "</rect>"
    )
    y = top + PAD
    tag = canvas.lines(LEFT + PAD, y, ["MYTH"], TEXT_PX, look.muted, bold=True)[0]
    belief, myth_bottom = canvas.lines(TEXT_X, y, myth, TEXT_PX, look.muted)
    strikes = []
    for row, line in enumerate(myth):
        mid = fmt(y + row * leading(TEXT_PX) + (ASCENT - 0.28) * TEXT_PX)  # through the x-height
        width = text_width(line, TEXT_PX)
        dash = fmt(width + 2)  # a little longer than the line so the draw never stops short
        at = fact_at + 0.1 * row
        strikes.append(
            f'<line x1="{TEXT_X}" y1="{mid}" x2="{fmt(TEXT_X + width)}" y2="{mid}" '
            f'stroke="{look.accent}" stroke-width="4" stroke-linecap="round" '
            f'stroke-dasharray="{dash}" stroke-dashoffset="{dash}">'
            + canvas.anim("stroke-dashoffset", [(at, dash), (at + 0.4, "0")], ease=TRAVEL)
            + "</line>"
        )
    fact_top = myth_bottom + TAG_GAP
    label = canvas.lines(LEFT + PAD, fact_top, ["FACT"], TEXT_PX, look.accent_text, bold=True)[0]
    truth, _ = canvas.lines(TEXT_X, fact_top, fact, TEXT_PX, look.text)
    reveal = f'<g opacity="0">{canvas.fade(fact_at + 0.2)}{"".join([*label, *truth])}</g>'
    body = [rect, *tag, *belief, *strikes, reveal]
    return canvas.reveal(body, appear, dim=(done, undim))
