"""Shared kit for 1080x1920 animated Reel SVGs: type, color, one-clock SMIL, safe-area layout.

Text is fitted with conservative per-character widths modelled on DejaVu Sans, the widest
font in the stack, so a line never overflows when Linux CI falls back to it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from itertools import pairwise

WIDTH, HEIGHT = 1080, 1920
SAFE = (60, 250, 1020, 1600)  # x0, y0, x1, y1; Instagram's UI covers the rest
LEFT, RIGHT = 72, 1008
RISE = 20  # px an element travels upward while it fades in
FONT = "Inter, 'Segoe UI', 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif"
ASCENT, DESCENT = 0.8, 0.25  # of the font size, above and below the baseline
EASE = "0.22 1 0.36 1"
HOLD = "0 0 1 1"

BG = "#0b1020"
CARD = "#151d33"
TAKE = "#1b2f5c"
TEXT = "#f8fafc"
MUTED = "#c3cfe2"
ACCENT = "#60a5fa"
ACCENT_TEXT = "#93c5fd"
PACKET = "#e0f2fe"
TRACK = "#334155"  # decoration, always drawn below 50% opacity
INK = BG  # text on accent fills
TEXT_ON = {TEXT: (BG, CARD, TAKE), MUTED: (BG, CARD, TAKE), ACCENT_TEXT: (BG, CARD, TAKE)}
MARK_ON = {ACCENT: (BG, CARD, TAKE), MUTED: (BG,), PACKET: (BG, CARD)}
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


@dataclass
class Canvas:
    """Elements on one clock of `total` seconds, with every text box recorded for checks."""

    total: float
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
            splines = ";".join(HOLD if a == b else EASE for (_, a), (_, b) in pairwise(frames))
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

    def reveal(self, children: list[str], start: float, end: float | None = None) -> str:
        """A group that fades and rises into place at `start`."""
        body = "".join(children)
        return f'<g opacity="0">{self.fade(start, end)}{self.rise(start)}{body}</g>'

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
    ) -> str:
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
        return f"<text {attrs}>{escape(content, quote=False)}</text>"

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


def header(canvas: Canvas, kicker: str | None, hook: str) -> tuple[list[str], float]:
    """Kicker and hook, visible from the first frame (the Reel cover); returns the bottom."""
    top = SAFE[1] + 12
    parts = []
    if kicker:
        parts.append(
            canvas.text(LEFT, top + ASCENT * 36, kicker, 36, ACCENT_TEXT, bold=True, spacing=4)
        )
        top += 36 + 30
    try:
        size, hook_lines = fit(hook, (88, 80), RIGHT - LEFT, 2, bold=True)
    except LayoutError:
        size, hook_lines = fit(hook, (80,), RIGHT - LEFT, 3, bold=True)
    more, bottom = canvas.lines(LEFT, top, hook_lines, size, TEXT, bold=True)
    bar_y = bottom + 24
    parts += [
        *more,
        f'<rect x="{LEFT}" y="{fmt(bar_y)}" width="0" height="8" rx="4" fill="{ACCENT}">'
        + canvas.anim("width", [(0.3, "0"), (1.0, "160")])
        + "</rect>",
    ]
    return parts, bar_y + 8


def leading(size: float) -> float:
    """Baseline to baseline: tight for display type, open for reading sizes."""
    return size * (1.1 if size >= 64 else 1.22)


def block_height(lines: int, size: float) -> float:
    """Glyph top of the first line to the descender of the last, as Canvas.lines draws them."""
    return ASCENT * size + (lines - 1) * leading(size) + DESCENT * size


def takeaway_height(text: str) -> float:
    size, lines = fit(text, (50, 48), RIGHT - LEFT - 96, 3, bold=True)
    return block_height(len(lines), size) + 68


def takeaway(canvas: Canvas, top: float, text: str, start: float) -> tuple[str, float]:
    """Accent-edged card that fades in at `start`; returns the element and its bottom."""
    size, lines = fit(text, (50, 48), RIGHT - LEFT - 96, 3, bold=True)
    texts, _ = canvas.lines(LEFT + 56, top + 34, lines, size, TEXT, bold=True)
    height = takeaway_height(text)
    card = (
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{fmt(height)}" '
        f'rx="28" fill="{TAKE}"/>'
        f'<rect x="{LEFT + 22}" y="{fmt(top + 28)}" width="8" height="{fmt(height - 56)}" '
        f'rx="4" fill="{ACCENT}"/>'
    )
    return canvas.reveal([card, *texts], start), top + height


def document(canvas: Canvas, parts: list[str], label: str) -> str:
    """The finished file; raises LayoutError if any text box left the safe area."""
    canvas.check()
    title = escape(clean(label), quote=False)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-labelledby="kr-title" '
        f'font-family="{FONT}"><title id="kr-title">{title}</title>'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>{"".join(parts)}</svg>'
    )
