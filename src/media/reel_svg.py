"""Compose a 1080x1920 animated SVG for a Reel from a validated scene.

Self-contained SMIL on one clock: no scripts, external fonts or images. Every text box is
checked against the Reels safe area, and the first frame already shows the hook (it is the
default cover). The result is deterministic for a given scene and source line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.media import reel_svg_stats, reel_svg_steps, reel_svg_timeline
from src.media.svg_kit import Canvas, LayoutError, document

__all__ = ["LayoutError", "Reel", "compose"]


@dataclass(frozen=True)
class Reel:
    svg: str
    duration: float
    boxes: tuple[tuple[float, float, float, float], ...]


def _draw(scene: dict[str, Any], source_line: str | None, kicker: bool) -> Reel:
    kind = scene["kind"]
    if kind == "steps":
        canvas = Canvas(reel_svg_steps.duration(scene))
        parts = reel_svg_steps.compose(canvas, scene, kicker=kicker)
    elif kind == "stat":
        canvas = Canvas(reel_svg_stats.duration(scene))
        parts = reel_svg_stats.compose(canvas, scene, source_line, kicker=kicker)
    elif kind == "timeline":
        canvas = Canvas(reel_svg_timeline.duration(scene))
        parts = reel_svg_timeline.compose(canvas, scene, source_line, kicker=kicker)
    else:
        raise LayoutError(f"unknown scene kind {kind!r}")
    label = scene.get("hook") or scene["headline"]
    return Reel(document(canvas, parts, label), canvas.total, tuple(canvas.boxes))


def compose(scene: dict[str, Any], *, source_line: str | None = None) -> Reel:
    """The scene with its format kicker, or without it when that is what makes it fit."""
    try:
        return _draw(scene, source_line, kicker=True)
    except LayoutError:
        return _draw(scene, source_line, kicker=False)
