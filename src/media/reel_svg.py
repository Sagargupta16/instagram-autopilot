"""Compose a 1080x1920 animated SVG for a Reel from a validated scene.

Self-contained SMIL on one clock: no scripts, external fonts or images. Every text box is
checked against the Reels safe area, and the first frame already shows the hook. `cover` is
the moment the whole scene is on screen (the final hold plus half a second, before the end
card), which the publisher passes to Instagram as the cover frame. `beats` are the moments
each narration line starts, and `pace` (from the narration) lengthens beats to fit their
lines. `handle` is the account name on the end card (None shows the follow line alone). The
result is deterministic for a given scene, source line, look, pace and handle.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.media import (
    reel_svg_myths,
    reel_svg_stats,
    reel_svg_steps,
    reel_svg_timeline,
    reel_svg_versus,
)
from src.media.svg_kit import Canvas, LayoutError
from src.media.svg_look import look as pick_look
from src.media.svg_parts import COVER_AFTER_HOLD, document

__all__ = ["LayoutError", "Reel", "compose", "length"]

LAYOUTS = {
    "steps": reel_svg_steps,
    "stat": reel_svg_stats,
    "timeline": reel_svg_timeline,
    "versus": reel_svg_versus,
    "myths": reel_svg_myths,
}
WITHOUT_SOURCE = {"steps", "versus"}  # evergreen explainers that draw no source line


@dataclass(frozen=True)
class Reel:
    svg: str
    duration: float
    boxes: tuple[tuple[float, float, float, float], ...]
    cover: float
    beats: tuple[float, ...] = ()

    @property
    def thumb_offset_ms(self) -> int:
        return round(self.cover * 1000)


def _without_icons(scene: dict[str, Any]) -> dict[str, Any]:
    bare = copy.deepcopy(scene)
    bare.pop("icon", None)
    sides = [bare[side] for side in ("left", "right") if side in bare]
    for item in [*bare.get("steps", []), *bare.get("milestones", []), *sides]:
        item.pop("icon", None)
    return bare


def _draw(
    scene: dict[str, Any],
    source_line: str | None,
    kicker: bool,
    look: int,
    pace: Sequence[float] = (),
    handle: str | None = None,
) -> Reel:
    kind = scene["kind"]
    if kind not in LAYOUTS:
        raise LayoutError(f"unknown scene kind {kind!r}")
    layout = LAYOUTS[kind]
    canvas = Canvas(layout.duration(scene, pace), pick_look(look))
    if kind in WITHOUT_SOURCE:
        parts = layout.compose(canvas, scene, kicker=kicker, pace=pace)
    else:
        parts = layout.compose(canvas, scene, source_line, kicker=kicker, pace=pace)
    label = scene.get("hook") or scene["headline"]
    cover = layout.hold_start(scene, pace) + COVER_AFTER_HOLD
    svg = document(canvas, parts, label, handle)
    return Reel(svg, canvas.total, tuple(canvas.boxes), cover, tuple(layout.beats(scene, pace)))


def length(scene: dict[str, Any], pace: Sequence[float] = ()) -> float:
    """Seconds the Reel for `scene` runs at this narration pace, without drawing it."""
    return LAYOUTS[scene["kind"]].duration(scene, pace)


def compose(
    scene: dict[str, Any],
    *,
    source_line: str | None = None,
    look: int = 0,
    pace: Sequence[float] = (),
    handle: str | None = None,
) -> Reel:
    """The scene with its kicker and icons; without the kicker, then without icons, when
    that is what makes it fit (both are optional decoration)."""
    try:
        return _draw(scene, source_line, True, look, pace, handle)
    except LayoutError:
        pass
    try:
        return _draw(scene, source_line, False, look, pace, handle)
    except LayoutError:
        return _draw(_without_icons(scene), source_line, False, look, pace, handle)
