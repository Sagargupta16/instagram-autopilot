"""Icons, looks, the hook entrance, progress bar, end card and cover frame of SVG Reels."""

from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.media import lucide, svg_kit
from src.media.reel_svg import LAYOUTS, compose
from src.media.svg_look import LOOKS
from src.media.svg_parts import END_S, FOLLOW

NS = "{http://www.w3.org/2000/svg}"
SAMPLES = Path(__file__).resolve().parents[2] / "scripts" / "samples" / "svg_reel_scenes.json"
BY_NAME = {item["name"]: item for item in json.loads(SAMPLES.read_text("utf-8"))["scenes"]}
ICON = re.compile(
    r'<g transform="translate\(([\d.]+) ([\d.]+)\) scale\(([\d.]+)\)" fill="none" '
    r'stroke="(#[0-9a-f]{6})" stroke-width="1.75"'
)
HANDLE = "@sample.account"


def built(name: str, look: int | None = None, handle: str | None = None):
    item = BY_NAME[name]
    chosen = item["look"] if look is None else look
    return compose(item["scene"], source_line=item["source_line"], look=chosen, handle=handle)


def times(element: ET.Element) -> list[float]:
    return [float(t) for t in element.get("keyTimes").split(";")]


def test_vendored_icons_are_a_curated_stroke_only_set_with_their_license() -> None:
    assert 40 <= len(lucide.ICONS) <= 60
    assert tuple(lucide.ICONS) == lucide.NAMES
    allowed = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
    for name, markup in lucide.ICONS.items():
        assert re.fullmatch(r"[a-z]+(?:-[a-z]+)*", name), name  # no digits: never a number
        root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{markup}</svg>')
        assert {child.tag.removeprefix(NS) for child in root} <= allowed, name
        for banned in ("fill", "style", "href"):
            assert banned not in markup, name
    license_text = (Path(lucide.__file__).parent / "LICENSE").read_text("utf-8")
    assert "ISC License" in license_text
    assert "Lucide" in license_text
    assert "MIT" in license_text  # the Feather-derived icons


@pytest.mark.parametrize("name", ["steps-cicd", "steps-six"])
def test_step_icons_are_at_least_96_px_in_the_accent(name) -> None:
    reel = built(name)
    look = LOOKS[BY_NAME[name]["look"]]
    icons = ICON.findall(reel.svg)
    steps = BY_NAME[name]["scene"]["steps"]
    assert len(icons) == len(steps) + 1  # one per step plus the end card
    for _, _, scale, color in icons[:-1]:
        assert float(scale) * 24 >= 96
        assert color == look.accent


@pytest.mark.parametrize(
    ("name", "count"),
    [("timeline-hubble", 5), ("stat-big-number", 1), ("stat-bars", 1), ("stat-line", 1)],
)
def test_milestones_and_stat_headlines_draw_their_icon(name, count) -> None:
    assert len(ICON.findall(built(name).svg)) == count + 1


def test_steps_without_icons_show_their_number_on_the_tile() -> None:
    scene = copy.deepcopy(BY_NAME["steps-cicd"]["scene"])
    for step in scene["steps"]:
        step.pop("icon")
    reel = compose(scene)
    numbers = [e for e in ET.fromstring(reel.svg).iter(f"{NS}text") if e.text and e.text.isdigit()]
    assert [e.text for e in numbers] == [str(i + 1) for i in range(len(scene["steps"]))]
    assert all(float(e.get("font-size")) >= 56 for e in numbers)
    assert len(ICON.findall(reel.svg)) == 1


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_hook_is_readable_on_the_first_frame_and_brightens_word_by_word(name) -> None:
    reel = built(name)
    look = LOOKS[BY_NAME[name]["look"]]
    root = ET.fromstring(reel.svg)
    parents = {child: parent for parent in root.iter() for child in parent}
    hook_lines = [e for e in root.iter(f"{NS}text") if list(e.iter(f"{NS}tspan"))]
    assert hook_lines
    starts = []
    for line in hook_lines:
        assert float(line.get("font-size")) >= 68
        node = line
        while node in parents:  # nothing above the hook starts hidden
            node = parents[node]
            assert node.get("opacity") != "0"
        for span in line.iter(f"{NS}tspan"):
            assert span.get("fill") == look.muted  # its first-frame color passes 4.5:1
            (shade,) = span.iter(f"{NS}animate")
            values = shade.get("values").split(";")
            assert values[0] == look.muted
            assert values[-1] == look.text
            starts.append(times(shade)[1])
    assert starts == sorted(starts)
    assert starts[-1] < 2.0 / reel.duration  # the whole entrance fits the opening seconds


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_hook_pop_never_leaves_the_safe_area(name) -> None:
    root = ET.fromstring(built(name).svg)
    parents = {child: parent for parent in root.iter() for child in parent}
    for pulse in root.iter(f"{NS}animateTransform"):
        if pulse.get("type") != "scale" or not list(parents[pulse].iter(f"{NS}text")):
            continue  # hinges, flips, the ring's tilt and the floor scale shapes, never text
        factors = [float(f) for value in pulse.get("values").split(";") for f in value.split()]
        assert max(factors) <= 1.15
        texts_squashed = min(factors) < 1 and pulse.get("values").split(";")[0] != "0"
        assert not texts_squashed  # text only ever pops from nothing or grows, never thins
    for line in (e for e in root.iter(f"{NS}text") if list(e.iter(f"{NS}tspan"))):
        pulse = next(parents[parents[line]].iter(f"{NS}animateTransform"))
        peak = max(float(v) for v in pulse.get("values").split(";"))
        size = float(line.get("font-size"))
        width = svg_kit.text_width("".join(line.itertext()), size, bold=True)
        assert float(line.get("x")) + width * peak <= svg_kit.SAFE[2]
        assert float(line.get("y")) - svg_kit.ASCENT * size * peak >= svg_kit.SAFE[1]


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_progress_bar_fills_over_the_whole_reel_inside_the_safe_area(name) -> None:
    reel = built(name)
    root = ET.fromstring(reel.svg)
    bars = [
        rect
        for rect in root.iter(f"{NS}rect")
        for anim in rect.iter(f"{NS}animate")
        if anim.get("calcMode") == "linear" and anim.get("attributeName") == "width"
    ]
    (bar,) = bars
    (fill,) = bar.iter(f"{NS}animate")
    assert fill.get("values") == f"0;{svg_kit.RIGHT - svg_kit.LEFT}"
    assert fill.get("keyTimes") == "0;1"
    assert float(fill.get("dur").removesuffix("s")) == pytest.approx(reel.duration)
    top = float(bar.get("y"))
    assert top >= svg_kit.SAFE[1]
    assert top + float(bar.get("height")) <= svg_kit.SAFE[1] + 20
    assert float(bar.get("x")) >= svg_kit.SAFE[0]


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_end_card_shows_the_handle_in_the_last_two_seconds(name) -> None:
    reel = built(name, handle=HANDLE)
    root = ET.fromstring(reel.svg)
    texts = {e.text: e for e in root.iter(f"{NS}text")}
    assert FOLLOW == "Follow for more facts"
    parents = {child: parent for parent in root.iter() for child in parent}
    card = parents[texts[HANDLE]]
    assert parents[texts[FOLLOW]] is card
    fade = next(card.iter(f"{NS}animate"))
    assert times(fade)[1] == pytest.approx((reel.duration - END_S + 0.15) / reel.duration, 1e-3)
    scene = root[2]  # title, background, then the scene group that dims behind the card
    dim = next(a for a in scene if a.tag == f"{NS}animate")
    assert dim.get("values").split(";")[-1] == "0.08"
    assert times(dim)[1] == pytest.approx((reel.duration - END_S) / reel.duration, 1e-3)


@pytest.mark.parametrize("handle", [None, "@" + "w" * 30])
def test_end_card_without_a_usable_handle_shows_the_follow_line_alone(handle) -> None:
    root = ET.fromstring(built("steps-cicd", handle=handle).svg)
    texts = [e.text for e in root.iter(f"{NS}text")]
    assert FOLLOW in texts
    assert not any(text and text.startswith("@") for text in texts)


def test_a_long_handle_steps_down_and_stays_on_one_line() -> None:
    handle = "@facts.in.motion.daily.explain"
    root = ET.fromstring(built("steps-cicd", handle=handle).svg)
    (line,) = [e for e in root.iter(f"{NS}text") if e.text == handle]
    assert float(line.get("font-size")) < 56


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_cover_frame_is_the_complete_scene_before_the_end_card(name) -> None:
    item = BY_NAME[name]
    reel = built(name)
    layout = LAYOUTS[item["scene"]["kind"]]
    hold = layout.hold_start(item["scene"])
    assert reel.cover == pytest.approx(hold + 0.5)
    assert reel.cover <= reel.duration - END_S - 0.5
    assert reel.thumb_offset_ms == round(reel.cover * 1000)
    assert isinstance(reel.thumb_offset_ms, int)


def test_cover_follows_the_last_reveal_of_each_layout() -> None:
    steps = BY_NAME["steps-cicd"]["scene"]
    take_at = 2.5 + 2.2 * len(steps["steps"])
    assert built("steps-cicd").cover >= take_at + 0.35 + 0.35  # the takeaway is in
    timeline = BY_NAME["timeline-hubble"]["scene"]
    assert built("timeline-hubble").cover >= 2.5 + 2.2 * len(timeline["milestones"]) + 0.75


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_each_look_is_deterministic_and_different(name) -> None:
    svgs = [built(name, look).svg for look in range(len(LOOKS))]
    assert svgs[0] == built(name, 0).svg
    assert len(set(svgs)) == len(LOOKS)
    for look, svg in zip(LOOKS, svgs, strict=True):
        assert look.accent in svg
        assert look.kicker(BY_NAME[name]["scene"]["kind"]) in svg
    assert built(name, len(LOOKS)).svg == svgs[0]  # the index wraps


def test_dimmed_steps_come_back_for_the_takeaway() -> None:
    reel = built("steps-cicd")
    root = ET.fromstring(reel.svg)
    dims = [
        a
        for a in root.iter(f"{NS}animate")
        if a.get("attributeName") == "opacity" and "0.7" in a.get("values").split(";")
    ]
    steps = len(BY_NAME["steps-cicd"]["scene"]["steps"])
    assert len(dims) == steps - 1  # every step but the last dims while a later one is active
    for anim in dims:
        assert anim.get("values").split(";")[-1] == "1"
