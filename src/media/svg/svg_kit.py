"""Shared kit for 1080x1920 animated Reel SVGs: type, one-clock SMIL and safe-area layout.

Text is fitted with conservative per-character widths modelled on DejaVu Sans, the widest
font in the stack, so a line never overflows when Linux CI falls back to it. Colors come
from the Canvas look (svg_look.py); framing parts (header, takeaway, end card) live in
svg_parts.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from itertools import pairwise

from src.media.svg.svg_look import DIM, LOOKS, Look

WIDTH, HEIGHT = 1080, 1920
SAFE = (60, 250, 1020, 1600)  # x0, y0, x1, y1; Instagram's UI covers the rest
LEFT, RIGHT = 72, 1008
RISE = 20  # px an element travels upward while it fades in
FONT = "Inter, 'Segoe UI', 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif"
ASCENT, DESCENT = 0.8, 0.25  # of the font size, above and below the baseline
# Type scale in px as (preferred, minimum) where text shrinks to fit. Set smaller than the
# first Reels on the owner's ask (2026-10-18); contract 16's floors are these minimums.
HOOK_PX = (76, 68)
LABEL_PX = (48, 44)
DETAIL_PX = (34, 32)
TAKE_PX = (44, 42)
SMALL_PX = 32  # kicker, source line and chart labels: the smallest text anywhere
EASE = "0.22 1 0.36 1"  # entrances: fast out, soft landing
TRAVEL = "0.45 0 0.25 1"  # line draws and growth: even travel with gentle ends
SWING = "0.16 1 0.3 1"  # a card turning to face the viewer: quick, then a firm stop
HOLD = "0 0 1 1"
FIRST_S = 0.7  # the first step, row or milestone lights while the hook is still being read
MIN_S = 15.0  # every Reel runs at least this long; narration may lengthen it
EDGE_ON = "1 0.04"  # a card seen side-on, as thin as a line
_DASHES = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")


class LayoutError(ValueError):
    """The scene cannot be drawn inside the safe area at the minimum type sizes."""


def clean(text: str) -> str:
    """Model text as one plain line: no control characters, en/em dashes become hyphens."""
    text = _DASHES.sub("-", text)
    return " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())


# Advance widths in 1/1000 em for ASCII 32-126: the widest of DejaVu Sans, Liberation Sans
# (Arial metrics) and Segoe UI, measured from the font files. Bold first, then regular.
_ASCII_BOLD = (
    "348 456 521 838 696 1002 872 306 457 457 523 838 380 415 380 443 696 696 696 696 696 696 "
    "696 696 696 696 400 400 838 838 838 611 1000 774 762 734 830 683 683 821 837 372 556 775 "
    "637 995 837 850 733 850 770 720 682 812 774 1103 771 724 725 457 436 457 838 556 500 675 "
    "716 593 716 678 435 716 712 343 343 665 343 1042 712 687 716 716 493 595 478 712 652 924 "
    "645 652 582 712 365 712 838"
)
_ASCII_REGULAR = (
    "318 401 460 838 636 950 800 275 390 390 500 838 318 400 318 390 636 636 636 636 636 636 "
    "636 636 636 636 337 337 838 838 838 556 1015 684 686 722 770 667 611 778 752 295 500 667 "
    "557 898 748 787 667 787 722 667 611 732 684 989 685 667 685 390 379 390 838 556 500 613 "
    "635 550 635 615 352 635 634 278 278 579 278 974 634 612 635 635 411 521 392 634 592 818 "
    "592 592 525 636 337 636 838"
)
_WIDTHS = {
    bold: {chr(32 + i): int(w) / 1000 for i, w in enumerate(table.split())}
    for bold, table in ((True, _ASCII_BOLD), (False, _ASCII_REGULAR))
}
MARGIN = 1.03  # hinting and kerning slack on top of the measured advances


def char_em(ch: str, bold: bool) -> float:
    if ch in _WIDTHS[bold]:
        return _WIDTHS[bold][ch] * MARGIN
    if ord(ch) >= 0x2E80:  # CJK and other full-width scripts
        return 1.04
    return 0.9 if bold else 0.85


def text_width(text: str, size: float, *, bold: bool = False, spacing: float = 0.0) -> float:
    return sum(char_em(ch, bold) * size + spacing for ch in text)


def wrap(text: str, size: float, width: float, *, bold: bool = False) -> list[str]:
    """Greedy word wrap; a word wider than the line is split by characters."""
    lines: list[str] = []
    current = ""
    for word in clean(text).split(" "):
        while text_width(word, size, bold=bold) > width:
            cut = max(
                i for i in range(1, len(word) + 1) if text_width(word[:i], size, bold=bold) <= width
            )
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:cut])
            word = word[cut:]
        candidate = f"{current} {word}".strip()
        if current and text_width(candidate, size, bold=bold) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def fit(
    text: str, sizes: tuple[float, ...], width: float, max_lines: int, *, bold: bool = False
) -> tuple[float, list[str]]:
    """The largest size whose wrap fits max_lines."""
    for size in sizes:
        lines = wrap(text, size, width, bold=bold)
        if len(lines) <= max_lines:
            return size, lines
    raise LayoutError(f'"{clean(text)[:40]}" is too long to fit; shorten it')


def fmt(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") or "0"


def leading(size: float) -> float:
    """Baseline to baseline: tight for display type, open for reading sizes."""
    return size * (1.1 if size >= 64 else 1.22)


def block_height(lines: int, size: float) -> float:
    """Glyph top of the first line to the descender of the last, as Canvas.lines draws them."""
    return ASCENT * size + (lines - 1) * leading(size) + DESCENT * size


@dataclass
class Canvas:
    """Elements on one clock of `total` seconds, with every text box recorded for checks."""

    total: float
    look: Look = LOOKS[0]
    boxes: list[tuple[float, float, float, float]] = field(default_factory=list)

    def key(self, seconds: float) -> str:
        return fmt(min(max(seconds / self.total, 0.0), 1.0))

    def anim(
        self,
        attr: str,
        frames: list[tuple[float, str]],
        *,
        tag: str = "animate",
        extra: str = "",
        discrete: bool = False,
        ease: str = EASE,
    ) -> str:
        """frames are (seconds, value); the first value holds from 0 and the last to the end."""
        if frames[0][0] > 0:
            frames = [(0.0, frames[0][1]), *frames]
        if frames[-1][0] < self.total:
            frames = [*frames, (self.total, frames[-1][1])]
        times = ";".join(self.key(t) for t, _ in frames)
        values = ";".join(value for _, value in frames)
        mode = 'calcMode="discrete"'
        if not discrete:
            splines = ";".join(HOLD if a == b else ease for (_, a), (_, b) in pairwise(frames))
            mode = f'calcMode="spline" keySplines="{splines}"'
        return (
            f'<{tag} attributeName="{attr}" {extra}dur="{fmt(self.total)}s" fill="freeze" '
            f'{mode} keyTimes="{times}" values="{values}"/>'
        )

    def fade(self, start: float, end: float | None = None, *, seconds: float = 0.35) -> str:
        """Opacity in at `start`, optionally out again at `end`."""
        frames = [(start, "0"), (start + seconds, "1")]
        if end is not None:
            frames += [(end, "1"), (end + 0.25, "0")]
        return self.anim("opacity", frames)

    def rise(self, start: float, *, seconds: float = 0.35) -> str:
        return self.anim(
            "transform",
            [(start, f"0 {RISE}"), (start + seconds, "0 0")],
            tag="animateTransform",
            extra='type="translate" ',
        )

    def dimming(self, done: float, undim: float) -> list[tuple[float, str]]:
        """Opacity frames that dim a finished element at `done` and restore it at `undim`."""
        if done + 0.3 >= undim:
            return []
        return [(done, "1"), (done + 0.3, fmt(DIM)), (undim, fmt(DIM)), (undim + 0.3, "1")]

    def reveal(
        self,
        children: list[str],
        start: float,
        end: float | None = None,
        *,
        dim: tuple[float, float] | None = None,
    ) -> str:
        """A group that fades and rises into place at `start`; `dim` is (done, undim)."""
        body = "".join(children)
        if dim is None:
            return f'<g opacity="0">{self.fade(start, end)}{self.rise(start)}{body}</g>'
        frames = [(start, "0"), (start + 0.35, "1"), *self.dimming(*dim)]
        return f'<g opacity="0">{self.anim("opacity", frames)}{self.rise(start)}{body}</g>'

    def scaled(
        self,
        x: float,
        y: float,
        frames: list[tuple[float, str]],
        body: str,
        *,
        also: str = "",
        ease: str = EASE,
    ) -> str:
        """`body` scaled about (x, y) by the factors in `frames` (it never moves otherwise);
        `also` is another animation for the same group, such as its opacity."""
        pulse = self.anim(
            "transform", frames, tag="animateTransform", extra='type="scale" ', ease=ease
        )
        return (
            f'<g transform="translate({fmt(x)} {fmt(y)})"><g>{pulse}{also}'
            f'<g transform="translate({fmt(-x)} {fmt(-y)})">{body}</g></g></g>'
        )

    def swing(self, x: float, y: float, start: float, body: str, seconds: float = 0.55) -> str:
        """`body` (a card's shapes, never its text) turns on a hinge through (x, y) from
        side-on at `start` to facing the viewer `seconds` later."""
        return self.scaled(x, y, [(start, EDGE_ON), (start + seconds, "1 1")], body, ease=SWING)

    def flip(self, x: float, y: float, at: float, body: str) -> str:
        """`body` turns over about the horizontal line through (x, y) at `at`, as a card shows
        its other side: side-on after 0.22 s, facing the viewer again after 0.5 s."""
        frames = [(at, "1 1"), (at + 0.22, EDGE_ON), (at + 0.5, "1 1")]
        return self.scaled(x, y, frames, body, ease=SWING)

    def text(
        self,
        x: float,
        y: float,
        content: str,
        size: float,
        fill: str,
        *,
        bold: bool = False,
        anchor: str = "start",
        spacing: float = 0.0,
        body: str | None = None,
    ) -> str:
        """One line of text; `body` replaces the escaped content (word tspans of the same text)."""
        content = clean(content)
        width = text_width(content, size, bold=bold, spacing=spacing)
        x0 = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        self.boxes.append((x0, y - ASCENT * size, x0 + width, y + DESCENT * size))
        attrs = f'x="{fmt(x)}" y="{fmt(y)}" font-size="{fmt(size)}" fill="{fill}"'
        if bold:
            attrs += ' font-weight="700"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if spacing:
            attrs += f' letter-spacing="{fmt(spacing)}"'
        return f"<text {attrs}>{escape(content, quote=False) if body is None else body}</text>"

    def lines(
        self, x: float, top: float, lines: list[str], size: float, fill: str, *, bold: bool = False
    ) -> tuple[list[str], float]:
        """Lines whose glyph tops start at `top`; returns the elements and the bottom edge."""
        out = [
            self.text(x, top + ASCENT * size + i * leading(size), line, size, fill, bold=bold)
            for i, line in enumerate(lines)
        ]
        return out, top + block_height(len(lines), size)

    def check(self) -> None:
        x0, y0, x1, y1 = SAFE
        for left, top, right, bottom in self.boxes:
            if left < x0 or right > x1 or top < y0 or bottom + RISE > y1:
                raise LayoutError("text would leave the Reels safe area; shorten the scene text")
