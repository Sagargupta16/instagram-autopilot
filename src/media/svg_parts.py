"""Framing every SVG Reel shares: progress bar, header with the hook entrance, takeaway card,
icons, the end card and the finished document.

The hook is fully readable on the first frame (muted, which still passes 4.5:1) and each
word brightens in turn while its line pops in scale, never past the safe area. The end card
fills the last END_S seconds: the scene dims behind the account handle.
"""

from __future__ import annotations

from html import escape

from src.media.lucide import ICONS
from src.media.svg_depth import HORIZON, cubes, floor
from src.media.svg_kit import (
    ASCENT,
    FONT,
    HEIGHT,
    HOOK_PX,
    LEFT,
    RIGHT,
    SAFE,
    SMALL_PX,
    TAKE_PX,
    WIDTH,
    Canvas,
    LayoutError,
    block_height,
    clean,
    fit,
    fmt,
    leading,
    text_width,
)

FOLLOW = "Follow for more facts"
HANDLE_PX = (56, 48, 40)  # a long username steps down; one that still overflows is dropped
END_S = 2.0  # the end card covers the last END_S seconds of every Reel
COVER_AFTER_HOLD = 0.5  # the cover frame: this long after the final hold starts
BAR_Y, BAR_H = SAFE[1] + 6, 8
HEADER_TOP = SAFE[1] + 36
WORD_S, LINE_S = 0.09, 0.22  # hook entrance stagger per word and per line
END_DIM = "0.08"


def progress(canvas: Canvas) -> str:
    """A thin bar inside the top of the safe area that fills over the whole Reel."""
    look, width = canvas.look, RIGHT - LEFT
    return (
        f'<rect x="{LEFT}" y="{BAR_Y}" width="{width}" height="{BAR_H}" rx="4" '
        f'fill="{look.track}" fill-opacity="0.45"/>'
        f'<rect x="{LEFT}" y="{BAR_Y}" width="0" height="{BAR_H}" rx="4" fill="{look.accent}">'
        f'<animate attributeName="width" dur="{fmt(canvas.total)}s" fill="freeze" '
        f'calcMode="linear" keyTimes="0;1" values="0;{width}"/></rect>'
    )


def _hook_line(canvas: Canvas, y: float, line: str, size: float, first_word: int, row: int) -> str:
    look = canvas.look
    words = clean(line).split(" ")
    spans = []
    for j, word in enumerate(words):
        at = 0.12 + WORD_S * (first_word + j)
        brighten = [(at, look.muted), (at + 0.12, look.accent_text), (at + 0.42, look.text)]
        tail = " " if j < len(words) - 1 else ""
        spans.append(
            f'<tspan fill="{look.muted}">{canvas.anim("fill", brighten)}'
            f"{escape(word + tail, quote=False)}</tspan>"
        )
    element = canvas.text(LEFT, y, line, size, look.text, bold=True, body="".join(spans))
    width = text_width(clean(line), size, bold=True)
    peak = min(1.08, (SAFE[2] - 1 - LEFT) / width)  # its scaled box stays in the safe area
    start = 0.1 + LINE_S * row
    pop = [(start, "1"), (start + 0.18, fmt(peak)), (start + 0.46, "1")]
    return canvas.scaled(LEFT, y, pop, element)


def header(canvas: Canvas, kicker: str | None, hook: str) -> tuple[list[str], float]:
    """Kicker and hook, readable from the first frame; returns the elements and the bottom."""
    look = canvas.look
    top = HEADER_TOP
    parts = []
    if kicker:
        parts.append(
            canvas.text(
                LEFT,
                top + ASCENT * SMALL_PX,
                kicker,
                SMALL_PX,
                look.accent_text,
                bold=True,
                spacing=4,
            )
        )
        top += SMALL_PX + 24
    try:
        size, hook_lines = fit(hook, HOOK_PX, RIGHT - LEFT, 2, bold=True)
    except LayoutError:
        size, hook_lines = fit(hook, HOOK_PX[-1:], RIGHT - LEFT, 3, bold=True)
    count = 0
    for row, line in enumerate(hook_lines):
        y = top + ASCENT * size + row * leading(size)
        parts.append(_hook_line(canvas, y, line, size, count, row))
        count += len(line.split(" "))
    bar_y = top + block_height(len(hook_lines), size) + 20
    sweep = canvas.anim("width", [(0.25, "0"), (0.25 + 0.12 * count + 0.5, "240")])
    parts.append(
        f'<rect x="{LEFT}" y="{fmt(bar_y)}" width="0" height="8" rx="4" fill="{look.accent}">'
        f"{sweep}</rect>"
    )
    return parts, bar_y + 8


def takeaway_height(text: str) -> float:
    size, lines = fit(text, TAKE_PX, RIGHT - LEFT - 96, 3, bold=True)
    return block_height(len(lines), size) + 68


def takeaway(canvas: Canvas, top: float, text: str, start: float) -> tuple[str, float]:
    """Accent-edged card that fades in at `start`; returns the element and its bottom."""
    look = canvas.look
    size, lines = fit(text, TAKE_PX, RIGHT - LEFT - 96, 3, bold=True)
    texts, _ = canvas.lines(LEFT + 56, top + 34, lines, size, look.text, bold=True)
    height = takeaway_height(text)
    card = canvas.swing(
        LEFT,
        top,
        start,
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{fmt(height)}" '
        f'rx="28" fill="{look.take}" stroke="{look.text}" stroke-opacity="0.10" stroke-width="2"/>'
        f'<rect x="{LEFT + 22}" y="{fmt(top + 28)}" width="8" height="{fmt(height - 56)}" '
        f'rx="4" fill="{look.accent}"/>',
    )
    return canvas.reveal([card, *texts], start), top + height


def icon(name: str, x: float, y: float, size: float, color: str) -> str:
    """A vendored Lucide icon with its top-left corner at (x, y), `size` px square."""
    return (
        f'<g transform="translate({fmt(x)} {fmt(y)}) scale({fmt(size / 24)})" fill="none" '
        f'stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICONS[name]}</g>"
    )


def tile(canvas: Canvas, cx: float, cy: float, radius: float, opacity: float = 0.16) -> str:
    """The soft accent shape behind an icon (decoration, below 50% opacity)."""
    look = canvas.look
    paint = f'fill="{look.accent}" fill-opacity="{fmt(opacity)}"'
    if look.tile == "circle":
        return f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(radius)}" {paint}/>'
    side, corner = 2 * radius, 0.3 * radius
    return (
        f'<rect x="{fmt(cx - radius)}" y="{fmt(cy - radius)}" width="{fmt(side)}" '
        f'height="{fmt(side)}" rx="{fmt(corner)}" {paint}/>'
    )


def _handle_line(canvas: Canvas, y: float, handle: str) -> str | None:
    try:
        size, (line,) = fit(handle, HANDLE_PX, RIGHT - LEFT - 96, 1, bold=True)
    except LayoutError:
        return None
    return canvas.text(540, y, line, size, canvas.look.text, bold=True, anchor="middle")


def end_card(canvas: Canvas, handle: str | None = None) -> str:
    """The account handle over the follow line, centred in the safe area for the last END_S
    seconds; without a handle (unknown, or too wide) the follow line takes its place."""
    look = canvas.look
    start = canvas.total - END_S
    cy = (SAFE[1] + SAFE[3]) / 2
    top, height = cy - 210, 420
    panel = canvas.swing(
        540,
        cy,
        start + 0.15,
        f'<rect x="{LEFT}" y="{fmt(top)}" width="{RIGHT - LEFT}" height="{height}" rx="36" '
        f'fill="{look.card}" stroke="{look.accent}" stroke-width="4"/>',
    )
    badge = tile(canvas, 540, top + 110, 64) + icon("users", 540 - 44, top + 66, 88, look.accent)
    name = _handle_line(canvas, top + 262, handle) if handle else None
    if name:
        lines = [name, canvas.text(540, top + 334, FOLLOW, 38, look.muted, anchor="middle")]
    else:
        lines = [canvas.text(540, top + 300, FOLLOW, 56, look.text, bold=True, anchor="middle")]
    return canvas.reveal([panel, badge, *lines], start + 0.15)


SOURCE_H = SMALL_PX + 6 + 28  # room a source line takes under the takeaway card
GHOST = 'fill-opacity="0.03" stroke-opacity="0.10" stroke-width="2"'  # the waiting layer


def ghost(canvas: Canvas, x: float, y: float, width: float, height: float, rx: float = 24) -> str:
    """A panel's waiting outline: visible from the first frame, lit later by its beat."""
    ink = canvas.look.text
    return (
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="{fmt(height)}" '
        f'rx="{fmt(rx)}" fill="{ink}" stroke="{ink}" {GHOST}/>'
    )


def ghost_dot(canvas: Canvas, cx: float, cy: float, radius: float) -> str:
    """A node's waiting outline on a rail."""
    ink = canvas.look.text
    return f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(radius)}" fill="{ink}" stroke="{ink}" {GHOST}/>'


def ghost_line(canvas: Canvas, x: float, y0: float, y1: float) -> str:
    """A connector's waiting path, drawn over later by the lit connector."""
    return (
        f'<line x1="{fmt(x)}" y1="{fmt(y0)}" x2="{fmt(x)}" y2="{fmt(y1)}" '
        f'stroke="{canvas.look.text}" stroke-opacity="0.10" stroke-width="3" stroke-linecap="round"/>'
    )


def wash(canvas: Canvas) -> str:
    """One soft tint glow where the story starts, the hook: 12% at its centre, fading out."""
    accent = canvas.look.accent
    return (
        f'<defs><radialGradient id="kr-wash" gradientUnits="userSpaceOnUse" cx="{LEFT + 240}" '
        f'cy="{HEADER_TOP + 140}" r="980"><stop offset="0" stop-color="{accent}" '
        f'stop-opacity="0.12"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/>'
        f'</radialGradient></defs><rect width="{WIDTH}" height="{HEIGHT}" fill="url(#kr-wash)"/>'
    )


def source(canvas: Canvas, card_bottom: float, text: str, start: float) -> str:
    """The adapter-named source line under the takeaway card, fading in at `start`."""
    line = canvas.text(
        LEFT, card_bottom + 28 + ASCENT * SMALL_PX, text, SMALL_PX, canvas.look.muted
    )
    return canvas.reveal([line], start)


def lattice(canvas: Canvas, step: int = 60) -> str:
    """A faint dot grid above the floor (decoration at 6% opacity, one static path)."""
    dots = "".join(
        f"M{x} {y}h0"
        for y in range(step // 2, HORIZON, step)  # the floor takes over below the horizon
        for x in range(step // 2, WIDTH, step)
    )
    return (
        f'<path d="{dots}" stroke="{canvas.look.text}" stroke-opacity="0.06" stroke-width="5" '
        'stroke-linecap="round" fill="none"/>'
    )


def dimmed(canvas: Canvas, parts: list[str]) -> str:
    """The scene, which fades back behind the end card."""
    start = canvas.total - END_S
    fade = canvas.anim("opacity", [(start, "1"), (start + 0.35, END_DIM)])
    return f"<g>{fade}{''.join(parts)}</g>"


def document(canvas: Canvas, parts: list[str], label: str, handle: str | None = None) -> str:
    """The finished file; raises LayoutError if any text box left the safe area."""
    back = [wash(canvas), lattice(canvas), floor(canvas), cubes(canvas)]
    body = dimmed(canvas, [*back, *parts]) + end_card(canvas, handle) + progress(canvas)
    canvas.check()
    title = escape(clean(label), quote=False)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-labelledby="kr-title" '
        f'font-family="{FONT}"><title id="kr-title">{title}</title>'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{canvas.look.bg}"/>{body}</svg>'
    )
