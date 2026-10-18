"""Composition rules for the animated SVG Reel: safety, type, layout, timing and contrast."""

from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

import pytest

from src.media import reel_svg, reel_svg_count, svg_kit
from src.media.reel_svg import Reel, compose
from src.media.svg_kit import LayoutError
from src.media.svg_look import DIM, LOOKS

NS = "{http://www.w3.org/2000/svg}"
SAMPLES = Path(__file__).resolve().parents[2] / "scripts" / "samples" / "svg_reel_scenes.json"
BY_NAME = {item["name"]: item for item in json.loads(SAMPLES.read_text("utf-8"))["scenes"]}
NAMES = sorted(BY_NAME)
DASHES = (chr(0x2013), chr(0x2014))
X0, Y0, X1, Y1 = svg_kit.SAFE
TEXTS = {f"{NS}text", f"{NS}tspan"}


@cache
def reel(name: str) -> Reel:
    item = BY_NAME[name]
    return compose(item["scene"], source_line=item["source_line"], look=item["look"])


def texts(svg: str) -> list[ET.Element]:
    return list(ET.fromstring(svg).iter(f"{NS}text"))


def words(element: ET.Element) -> str:
    """A text element's characters, including the hook's per-word tspans."""
    return "".join(element.itertext())


def run_of(elements: list[ET.Element], phrase: str) -> list[ET.Element]:
    """The consecutive text elements whose words make up `phrase` (wrapped lines)."""
    target = svg_kit.clean(phrase)
    for start in range(len(elements)):
        for end in range(start + 1, len(elements) + 1):
            joined = " ".join(words(element) for element in elements[start:end])
            if joined == target:
                return elements[start:end]
            if not target.startswith(joined):
                break
    raise AssertionError(f"no run of text elements spells {phrase!r}")


def size(element: ET.Element) -> float:
    return float(element.get("font-size"))


def inside(left: float, top: float, right: float, bottom: float) -> bool:
    return left >= X0 and right <= X1 and top >= Y0 and bottom + svg_kit.RISE <= Y1


@pytest.mark.parametrize("name", NAMES)
def test_sample_is_well_formed_and_labelled(name) -> None:
    root = ET.fromstring(reel(name).svg)
    assert root.tag == f"{NS}svg"
    assert root.get("viewBox") == "0 0 1080 1920"
    assert root.get("role") == "img"
    label = root.get("aria-labelledby")
    titles = [e for e in root.iter(f"{NS}title") if e.get("id") == label]
    assert len(titles) == 1
    assert titles[0].text


@pytest.mark.parametrize("name", NAMES)
def test_sample_is_inert_and_namespaced(name) -> None:
    svg = reel(name).svg
    tags = {element.tag.removeprefix(NS) for element in ET.fromstring(svg).iter()}
    assert not tags & {"script", "foreignObject", "image"}
    lowered = svg.lower()
    for banned in ("<script", "foreignobject", "<image", "url(", "@import", "@font-face"):
        assert banned not in lowered
    assert all(ref.startswith("#") for ref in re.findall(r'href\s*=\s*"([^"]*)"', svg))
    assert "prefers-reduced-motion" not in svg
    ids = [e.get("id") for e in ET.fromstring(svg).iter() if e.get("id")]
    assert ids
    assert all(value.startswith("kr-") for value in ids)


@pytest.mark.parametrize("name", NAMES)
def test_type_meets_size_floors(name) -> None:
    scene = BY_NAME[name]["scene"]
    elements = texts(reel(name).svg)
    for element in elements:
        assert size(element) >= 32, words(element)
    assert all(size(e) >= 68 for e in run_of(elements, scene.get("hook") or scene["headline"]))
    assert all(size(e) >= 42 for e in run_of(elements, scene["takeaway"]))
    for step in scene.get("steps", []):
        assert all(size(e) >= 44 for e in run_of(elements, step["label"]))
        assert all(size(e) >= 32 for e in run_of(elements, step["detail"]))


@pytest.mark.parametrize("name", NAMES)
def test_recorded_and_parsed_text_stay_in_safe_area(name) -> None:
    boxes = reel(name).boxes
    assert all(inside(*box) for box in boxes), [box for box in boxes if not inside(*box)]
    elements = texts(reel(name).svg)
    assert len(elements) == len(boxes) > 0
    for element in elements:
        x, y, px = float(element.get("x")), float(element.get("y")), size(element)
        width = svg_kit.text_width(
            words(element),
            px,
            bold=element.get("font-weight") == "700",
            spacing=float(element.get("letter-spacing", 0)),
        )
        anchor = element.get("text-anchor", "start")
        left = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        top, bottom = y - svg_kit.ASCENT * px, y + svg_kit.DESCENT * px
        assert inside(left, top, left + width, bottom), words(element)


@pytest.mark.parametrize("name", NAMES)
def test_duration_rules(name) -> None:
    scene, duration = BY_NAME[name]["scene"], reel(name).duration
    if scene["kind"] == "steps":
        assert duration == pytest.approx(2.5 + 2.2 * len(scene["steps"]) + 5.3)
    elif scene["kind"] == "timeline":
        assert duration == pytest.approx(2.5 + 2.2 * len(scene["milestones"]) + 5.3)
    else:
        assert duration >= 12
    assert 12 <= duration <= 21


@pytest.mark.parametrize("name", NAMES)
def test_compose_is_deterministic(name) -> None:
    item = copy.deepcopy(BY_NAME[name])
    first = compose(item["scene"], source_line=item["source_line"]).svg
    assert first == compose(item["scene"], source_line=item["source_line"]).svg


@pytest.mark.parametrize("name", NAMES)
def test_animations_share_one_clock(name) -> None:
    built = reel(name)
    root = ET.fromstring(built.svg)
    animations = [e for tag in ("animate", "animateTransform") for e in root.iter(f"{NS}{tag}")]
    assert animations
    for element in [*animations, *root.iter(f"{NS}animateMotion")]:
        assert float(element.get("dur").removesuffix("s")) == pytest.approx(built.duration)
        times = [float(t) for t in element.get("keyTimes").split(";")]
        assert times[0] == 0
        assert times[-1] == 1
        assert times == sorted(times)
        values = (element.get("values") or element.get("keyPoints")).split(";")
        assert len(times) == len(values)
        if element.get("calcMode") == "spline":
            assert len(element.get("keySplines").split(";")) == len(values) - 1


def test_dashes_in_wrapped_scene_text_become_hyphens() -> None:
    scene = copy.deepcopy(BY_NAME["steps-cicd"]["scene"])
    scene["hook"] = f"How CI{DASHES[1]}CD ships{DASHES[0]}fast"
    for step in scene["steps"]:
        step["label"] += DASHES[1] + "x"
        step["detail"] = step["detail"].replace(" ", f" {DASHES[1]} ", 1)
    scene["takeaway"] = f"Every commit {DASHES[0]} same path"
    svg = compose(scene).svg
    assert not any(dash in svg for dash in DASHES)
    assert "CI-CD" in svg


@pytest.mark.parametrize(
    ("sample", "parent", "field", "text"),
    [
        ("stat-bars", ("bars", 0), "label", f"Plat{DASHES[1]}form"),
        ("stat-bars", (), "unit", f"Deploys{DASHES[0]}year"),
        ("timeline-hubble", ("milestones", 0), "date", f"1946{DASHES[0]}47"),
        ("stat-bars", ("bars", 0), "label", "Plat\x0bform"),
    ],
    ids=["bar-label-em-dash", "unit-en-dash", "date-en-dash", "bar-label-control-char"],
)
def test_unwrapped_fields_are_cleaned_too(sample, parent, field, text) -> None:
    item = copy.deepcopy(BY_NAME[sample])
    target = item["scene"]
    for key in parent:
        target = target[key]
    target[field] = text
    svg = compose(item["scene"], source_line=item["source_line"]).svg
    ET.fromstring(svg)
    assert not any(dash in svg for dash in DASHES)


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def over(color: str, under: str, alpha: float) -> str:
    """`color` painted at `alpha` over `under`, as the browser composites a dimmed group."""
    top = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    bottom = [int(under[i : i + 2], 16) for i in (1, 3, 5)]
    mixed = (round(a * alpha + b * (1 - alpha)) for a, b in zip(top, bottom, strict=True))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


@pytest.mark.parametrize("look", LOOKS, ids=[look.name for look in LOOKS])
def test_every_look_meets_wcag_also_when_dimmed(look) -> None:
    assert contrast("#ffffff", "#000000") == pytest.approx(21)  # the helper itself
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)
    for fg, backgrounds in look.text_on().items():
        assert all(contrast(fg, bg) >= 4.5 for bg in backgrounds), fg
        dimmed = over(look.card, look.bg, DIM)
        assert contrast(over(fg, look.bg, DIM), dimmed) >= 4.5, fg
    for fg, backgrounds in look.mark_on().items():
        assert all(contrast(fg, bg) >= 3 for bg in backgrounds), fg
    assert contrast(over(look.accent, look.bg, DIM), over(look.card, look.bg, DIM)) >= 3
    assert contrast(look.ink, look.accent) >= 4.5
    tile = over(look.accent, look.card, 0.16)  # the icon tile under step icons and numbers
    assert contrast(look.accent, tile) >= 3
    assert contrast(look.accent_text, tile) >= 4.5


def test_looks_differ_and_name_every_kicker() -> None:
    assert len({look.accent for look in LOOKS}) == len(LOOKS) >= 3
    assert len({look.tile for look in LOOKS}) == 2
    for kind in ("steps", "stat", "timeline"):
        assert len({look.kicker(kind) for look in LOOKS}) == len(LOOKS)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("index", range(len(LOOKS)))
def test_text_fills_come_from_the_checked_palette(name, index) -> None:
    look = LOOKS[index]
    item = BY_NAME[name]
    svg = compose(item["scene"], source_line=item["source_line"], look=index).svg
    root = ET.fromstring(svg)
    fills = {element.get("fill") for element in root.iter() if element.tag in TEXTS}
    assert fills <= {*look.text_on(), look.ink}
    background = next(root.iter(f"{NS}rect"))
    assert background.get("fill") == look.bg
    assert (background.get("width"), background.get("height")) == ("1080", "1920")


def test_hostile_text_is_escaped() -> None:
    scene = copy.deepcopy(BY_NAME["steps-cicd"]["scene"])
    attack = "<script>alert(1)</script>"
    scene["hook"] = f'{attack} & "q" ]]>'
    scene["steps"][0]["label"] = '& "x" ]]>'
    scene["steps"][1]["label"] = "<b>"
    scene["steps"][1]["detail"] = f"{attack} & 'single' \"double\" ]]>"
    svg = compose(scene).svg
    root = ET.fromstring(svg)
    assert not [e for e in root.iter() if "script" in e.tag.lower()]
    assert "<script" not in svg
    assert "]]>" not in svg
    assert next(root.iter(f"{NS}title")).text == svg_kit.clean(scene["hook"])
    visible = " ".join(words(e) for e in root.iter(f"{NS}text"))
    assert "<b>" in visible
    assert "alert(1)" in visible


def test_oversized_scene_raises_layout_error() -> None:
    widest = {"label": "W" * 18, "detail": "W" * 64}
    scene = {"kind": "steps", "hook": "W" * 42, "steps": [widest] * 6, "takeaway": "W" * 70}
    with pytest.raises(LayoutError):
        compose(scene)


def test_compose_drops_the_kicker_when_that_makes_it_fit() -> None:
    scene = copy.deepcopy(BY_NAME["steps-six"]["scene"])
    scene["hook"] = "Www Mom Wakes Warm Machines Many Workers"
    for step in scene["steps"]:
        step["detail"] = "Www mom wakes warm machines many workers walk"
    scene["takeaway"] = "Www mom wakes warm machines many workers walk home when mows wow www"
    with pytest.raises(LayoutError):
        reel_svg._draw(scene, None, True, 0)
    built = compose(scene)
    assert "HOW IT WORKS" not in built.svg
    assert built.svg.count('stroke-width="1.75"') == len(scene["steps"]) + 1  # icons kept
    assert all(inside(*box) for box in built.boxes)
    assert "HOW IT WORKS" in reel("steps-cicd").svg


def test_compose_drops_icons_last_when_only_that_makes_it_fit() -> None:
    item = copy.deepcopy(BY_NAME["versus-tcp-udp"])
    scene = item["scene"]
    scene["hook"] = "Www Mom Wakes Warm Machines Many Workers"
    for row in scene["rows"]:
        row["left"] = row["right"] = "Www mom wakes warm machines many"
    scene["takeaway"] = "Www mom wakes warm machines many workers walk home when mows wow www"
    for kicker in (True, False):
        with pytest.raises(LayoutError):
            reel_svg._draw(scene, item["source_line"], kicker, 0)
    built = compose(scene, source_line=item["source_line"])
    assert built.svg.count('stroke-width="1.75"') == 1  # only the end card's icon
    assert scene["left"]["icon"] == "shield-check"  # the caller's scene is not changed


def test_wrap_never_exceeds_the_width() -> None:
    text = "Automated tests run, and any failure stops the pipeline before deploy"
    for px, bold in ((40, False), (88, True), (36, True)):
        lines = svg_kit.wrap(text, px, 600, bold=bold)
        assert len(lines) > 1
        assert all(svg_kit.text_width(line, px, bold=bold) <= 600 for line in lines)
        assert " ".join(lines) == text


def test_wrap_splits_a_word_longer_than_the_line() -> None:
    word = "W" * 30
    lines = svg_kit.wrap(f"ab {word} cd", 80, 300, bold=True)
    assert (lines[0], lines[-1]) == ("ab", "cd")
    assert len(lines) > 3
    assert "".join(lines[1:-1]) == word
    assert all(svg_kit.text_width(line, 80, bold=True) <= 300 for line in lines)


def test_fit_picks_the_largest_size_or_raises() -> None:
    assert svg_kit.fit("short hook", (88, 80), 936, 1, bold=True) == (88, ["short hook"])
    with pytest.raises(LayoutError, match="too long"):
        svg_kit.fit("W" * 100, (80, 60), 300, 2, bold=True)


def test_counting_keeps_suffix_grouping_and_decimals() -> None:
    percent = reel_svg_count.counting("62%")
    assert percent[-1] == "62%"
    assert all(frame.endswith("%") for frame in percent)
    assert [float(f[:-1]) for f in percent] == sorted(float(f[:-1]) for f in percent)
    grouped = reel_svg_count.counting("1,240")
    assert grouped[-1] == "1,240"
    assert all(re.fullmatch(r"\d{1,3}(,\d{3})*", frame) for frame in grouped)
    assert any("," in frame for frame in grouped[:-1])
    decimal = reel_svg_count.counting("3.8")
    assert decimal[-1] == "3.8"
    assert all(re.fullmatch(r"\d+\.\d", frame) for frame in decimal)


NUMBERS = {"62%": 62, "1,240": 1240, "12.5": 12.5, "1.5k": 1500, "2 million": 2e6}
NUMBERS |= {"$3bn": 3e9, "4tn": 4e12, "7 trillion": 7e12, "n/a": 0}


@pytest.mark.parametrize(("value", "expected"), NUMBERS.items())
def test_number_reads_suffixes(value, expected) -> None:
    assert reel_svg_count.number(value) == pytest.approx(expected)
