"""Depth behind every SVG Reel: a perspective floor that keeps gliding toward the viewer and
wireframe cubes floating in three parallax layers.

All of it is decoration drawn under the scene below 50% opacity, so it never changes what text
or marks sit on (contract 17). The floor's zoom and each cube layer's drift are one animation
each, and the nine turning cubes add one each. The floor's lines are spaced and weighted by a
constant ratio from the horizon, so zooming about the vanishing point by that ratio lands every
line on the next one and the loop has no seam. A cube looks the same every quarter turn, so a
turning cube loops through 90 degrees without a seam. The cubes are placed by a fixed seed, so
every Reel is deterministic.
"""

from __future__ import annotations

import math
import random

from src.media.svg_kit import HEIGHT, WIDTH, Canvas, fmt

HORIZON = 1180  # the floor's vanishing line, behind the lower half of the scene
VANISH = (WIDTH / 2, HORIZON)
RATIO, PERIOD = 1.38, 2.4  # the floor zooms by RATIO every PERIOD seconds
NEAREST = 6.0  # px below the horizon of the farthest floor line
RAIL_STEP = 150  # px between the floor's rails along the bottom edge
RAIL_TOP = 110  # px below the horizon where the rails start, short of their crowded meeting
LINEAR = "0 0 1 1"
# Cube size px, stroke opacity, upward drift px over the Reel, count and seconds per quarter
# turn (0 for still), far to near.
LAYERS = ((16, 0.18, 90, 6, 0), (24, 0.26, 190, 5, 9.0), (36, 0.36, 320, 4, 6.0))
TILT = math.radians(28)  # the cubes are seen from a little above
_CORNERS = [(cx, cy, cz) for cx in (-1, 1) for cy in (-1, 1) for cz in (-1, 1)]
_EDGES = [
    (a, b)
    for a in range(8)
    for b in range(a + 1, 8)
    if sum(p != q for p, q in zip(_CORNERS[a], _CORNERS[b], strict=True)) == 1
]
SEED = 20261024
CUBES_TOP = 640  # cubes start below the header and only rise toward the middle


def floor(canvas: Canvas) -> str:
    """Grid lines from the horizon to the bottom edge, gliding toward the viewer forever."""
    accent = canvas.look.accent
    cx, cy = VANISH
    rows, gap = [], NEAREST
    while gap < (HEIGHT - HORIZON) * RATIO:  # one line past the edge, so the zoom never runs dry
        y = fmt(HORIZON + gap)
        rows.append(
            f'<line x1="-80" y1="{y}" x2="{WIDTH + 80}" y2="{y}" stroke-width="{fmt(0.0045 * gap)}"/>'
        )
        gap *= RATIO
    repeats = math.ceil(canvas.total / PERIOD)
    zoom = (
        f'<animateTransform attributeName="transform" type="scale" values="1;{RATIO}" '
        f'dur="{PERIOD}s" repeatCount="{repeats}" calcMode="linear" fill="freeze"/>'
    )
    glide = (
        f'<g transform="translate({fmt(cx)} {cy})"><g>{zoom}'
        f'<g transform="translate({fmt(-cx)} {-cy})">{"".join(rows)}</g></g></g>'
    )
    rails = []
    reach = HEIGHT - HORIZON
    for k in range(-8, 9):
        bottom_x = cx + k * RAIL_STEP
        top_x = cx + k * RAIL_STEP * RAIL_TOP / reach
        rails.append(
            f'<line x1="{fmt(top_x)}" y1="{HORIZON + RAIL_TOP}" x2="{fmt(bottom_x)}" '
            f'y2="{HEIGHT}"/>'
        )
    return (
        f'<g fill="none" stroke="{accent}" stroke-opacity="0.3">{glide}</g>'
        f'<g fill="none" stroke="{accent}" stroke-opacity="0.16" stroke-width="2">'
        f"{''.join(rails)}</g>"
    )


def _wireframe(x: float, y: float, size: float, angle: float) -> str:
    """Path data of a cube centred on (x, y), turned `angle` radians about its upright axis and
    seen from TILT above: its twelve edges, always in the same order so frames interpolate."""
    half = 0.62 * size
    cos_t, sin_t = math.cos(angle), math.sin(angle)
    points = []
    for cx, cy, cz in _CORNERS:
        across, depth = cx * cos_t + cz * sin_t, -cx * sin_t + cz * cos_t
        up = cy * math.cos(TILT) - depth * math.sin(TILT)
        points.append((x + half * across, y - half * up))
    return "".join(
        f"M{points[a][0]:.1f} {points[a][1]:.1f}L{points[b][0]:.1f} {points[b][1]:.1f}"
        for a, b in _EDGES
    )


def _cube(x: float, y: float, size: float, spin: float, turn: float, repeats: int) -> str:
    """One cube at `spin` radians; with a `turn` (seconds per quarter turn, negative to turn
    the other way) it keeps turning for `repeats` quarter turns."""
    if not turn:
        return f'<path d="{_wireframe(x, y, size, spin)}"/>'
    frames = ";".join(
        _wireframe(x, y, size, spin + math.copysign(k * math.pi / 12, turn)) for k in range(7)
    )
    rotate = (
        f'<animate attributeName="d" values="{frames}" dur="{fmt(abs(turn))}s" '
        f'repeatCount="{repeats}" calcMode="linear" fill="freeze"/>'
    )
    return f'<path d="{_wireframe(x, y, size, spin)}">{rotate}</path>'


def cubes(canvas: Canvas) -> str:
    """Three layers of cubes rising at different speeds: the nearer, the larger and faster, and
    the near two layers turning. None starts above CUBES_TOP, so the hook's first frame has
    nothing behind it."""
    accent = canvas.look.accent
    placer = random.Random(SEED)  # NOSONAR -- fixed layout, not secrecy
    layers = []
    for size, opacity, drift, count, turn in LAYERS:
        repeats = math.ceil(canvas.total / turn) if turn else 0
        shapes = []
        for index in range(count):
            x = placer.uniform(60, WIDTH - 60)
            y = placer.uniform(CUBES_TOP + drift, HEIGHT + drift)
            spin = placer.uniform(0, math.pi / 2)
            direction = turn if index % 2 else -turn  # neighbours turn opposite ways
            shapes.append(_cube(x, y, size, spin, direction, repeats))
        rise = canvas.anim(
            "transform",
            [(0.0, "0 0"), (canvas.total, f"{fmt(drift / 6)} {fmt(-drift)}")],
            tag="animateTransform",
            extra='type="translate" ',
            ease=LINEAR,
        )
        layers.append(
            f'<g fill="none" stroke="{accent}" stroke-opacity="{opacity}" stroke-width="2.5" '
            f'stroke-linecap="round">{rise}{"".join(shapes)}</g>'
        )
    return "".join(layers)
