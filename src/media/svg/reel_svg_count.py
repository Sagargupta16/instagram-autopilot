"""Stat values as numbers and as count-up frames, for the big-number and ring Reels."""

from __future__ import annotations

import re

from src.media.svg.svg_kit import Canvas

STEPS = 24  # frames in a count-up
# Currency and suffix exclude digits, commas and dots, so no two groups can claim the same
# character and matching stays linear (SonarCloud S8786).
_VALUE = re.compile(r"(?P<cur>[^\d,.]?)(?P<num>[\d,]+)(?P<dec>\.\d+)?(?P<suf>[^\d,.]*)")


def number(value: str) -> float:
    """The magnitude used for scaling; suffix multipliers keep mixed bars comparable."""
    m = _VALUE.fullmatch(value)
    base = float(m["num"].replace(",", "") + (m["dec"] or "")) if m else 0.0
    suffix = (m["suf"] if m else "").strip().casefold()
    scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
    return base * scale.get(suffix, 1e12 if suffix in {"tn", "trillion"} else 1.0)


def counting(value: str, steps: int = STEPS) -> list[str]:
    """Count-up frames that share the final value's prefix, grouping, decimals and suffix."""
    m = _VALUE.fullmatch(value)
    if not m:
        return [value]
    final = float(m["num"].replace(",", "") + (m["dec"] or ""))
    decimals = len(m["dec"]) - 1 if m["dec"] else 0
    grouping = "," if "," in m["num"] else ""
    frames = []
    for j in range(1, steps):
        current = final * (1 - (1 - j / steps) ** 3)
        frames.append(f"{m['cur']}{current:{grouping}.{decimals}f}{m['suf']}")
    return [*frames, value]


def counter(
    canvas: Canvas, at: tuple[float, float], value: str, size: float, window: tuple[float, float]
) -> str:
    """Discrete count-up at `at` (x, y): each frame is its own text shown for one tick of the
    `window` (start, seconds)."""
    x, y = at
    start, seconds = window
    frames = counting(value)
    tick = seconds / len(frames)
    out = []
    for j, label in enumerate(frames):
        shown = [(0.0, "0"), (start + j * tick, "1")]
        if j < len(frames) - 1:
            shown.append((start + (j + 1) * tick, "0"))
        element = canvas.text(x, y, label, size, canvas.look.text, bold=True, anchor="middle")
        out.append(f'<g opacity="0">{canvas.anim("opacity", shown, discrete=True)}{element}</g>')
    return "".join(out)
