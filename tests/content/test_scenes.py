"""Scene contracts and grounding for the animated SVG Reel formats."""

from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from src.content.scenes import (
    StatScene,
    StepsScene,
    TimelineScene,
    scene_texts,
    source_line,
    validate_svg_content,
)
from src.media.lucide import ICONS
from src.media.reel_svg import LayoutError

WATER = {
    "title": "U.S. drinking water bills rose 62% in a decade",
    "source": "google_news",
    "publisher": "Reuters",
}
POWER = {"title": "Electricity prices climbed 64% since 2015", "source": "guardian"}
WIDE_HOOK = "WWW WWW WWW WWW WWW WWW WWW WWW WWW WWW WW"  # 42 chars, wider than three lines


def _steps(count: int = 3, **overrides: Any) -> dict[str, Any]:
    names = ("Resolve", "Connect", "Request", "Respond", "Render", "Cache", "Expire")
    steps = [{"label": name, "detail": f"The browser does the {name} part."} for name in names]
    return {
        "kind": "steps",
        "hook": "How does DNS find a website?",
        "steps": steps[:count],
        "takeaway": "A name becomes an address before anything loads.",
        **overrides,
    }


def _stat(variant: str = "big_number", **overrides: Any) -> dict[str, Any]:
    visual = {
        "big_number": {"value": "62%", "context": "Rise in U.S. drinking water bills in a decade"},
        "ring": {"value": "62%", "context": "Share of households on metered water"},
        "bars": {"bars": [{"label": "Rail", "value": "1,240"}, {"label": "Bus", "value": "2,010"}]},
        "line": {"points": [{"label": str(year), "value": "62%"} for year in (2015, 2020, 2025)]},
    }[variant]
    scene = {"kind": "stat", "variant": variant, "headline": "Water bills rose fast", **visual}
    return {**scene, "takeaway": "Bills grew faster than wages.", "source_index": 0, **overrides}


def _timeline(count: int = 4, **overrides: Any) -> dict[str, Any]:
    years = ("1957", "1961", "1969", "1972", "1990", "1998", "2011")
    return {
        "kind": "timeline",
        "hook": "The story of spaceflight",
        "milestones": [{"date": year, "event": f"Milestone in {year}"} for year in years[:count]],
        "takeaway": "Each step built on the last.",
        **overrides,
    }


def _valid(model: type[BaseModel], scene: dict[str, Any]) -> bool:
    try:
        model.model_validate(scene)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(("count", "ok"), [(2, False), (3, True), (6, True), (7, False)])
def test_steps_count_bounds_at_max_field_lengths(count: int, ok: bool) -> None:
    scene = _steps(count, hook="h" * 42, takeaway="t" * 70)
    scene["steps"][0] = {"label": "l" * 18, "detail": "d" * 48, "icon": "rocket"}
    assert _valid(StepsScene, scene) is ok


@pytest.mark.parametrize(
    "overrides",
    [
        {"hook": "h" * 43},
        {"takeaway": "t" * 71},
        {"steps": [{"label": "l" * 19, "detail": "Fine."}] * 3},
        {"steps": [{"label": "Fine", "detail": "d" * 49}] * 3},
        {"subtitle": "Extra key"},
        {"steps": [{"label": "Fine", "detail": "Fine.", "icon": "not-an-icon"}] * 3},
        {"steps": [{"label": "Fine", "detail": "Fine.", "icon": "Rocket"}] * 3},
        {"steps": [{"label": "Fine", "detail": "Fine.", "image": "rocket"}] * 3},
        {"hook": "   "},
    ],
)
def test_steps_rejects_long_blank_or_extra_fields(overrides: dict[str, Any]) -> None:
    assert not _valid(StepsScene, _steps(**overrides))


@pytest.mark.parametrize("name", sorted(ICONS))
def test_every_vendored_icon_name_validates(name: str) -> None:
    scene = _steps()
    scene["steps"][0]["icon"] = name
    assert StepsScene.model_validate(scene).steps[0].icon == name


def test_unknown_icon_is_a_repairable_error_naming_the_field() -> None:
    scene = _timeline()
    scene["milestones"][1]["icon"] = "spaceship"
    with pytest.raises(ValidationError, match="unknown icon 'spaceship'") as error:
        TimelineScene.model_validate(scene)
    assert error.value.errors()[0]["loc"] == ("milestones", 1, "icon")
    assert not _valid(StatScene, _stat(icon="spaceship"))
    assert StatScene.model_validate(_stat(icon="droplet")).icon == "droplet"


def test_icons_are_optional_everywhere() -> None:
    assert StepsScene.model_validate(_steps()).steps[0].icon is None
    assert TimelineScene.model_validate(_timeline()).milestones[0].icon is None
    assert StatScene.model_validate(_stat()).icon is None


@pytest.mark.parametrize(("length", "ok"), [(44, True), (45, False)])
def test_timeline_events_are_short(length: int, ok: bool) -> None:
    scene = _timeline()
    scene["milestones"][0]["event"] = "e" * length
    assert _valid(TimelineScene, scene) is ok


@pytest.mark.parametrize("variant", ["big_number", "ring", "bars", "line"])
def test_each_stat_variant_validates(variant: str) -> None:
    assert StatScene.model_validate(_stat(variant)).variant == variant


@pytest.mark.parametrize("missing", ["value", "context"])
@pytest.mark.parametrize("variant", ["big_number", "ring"])
def test_number_variants_need_value_and_context(variant: str, missing: str) -> None:
    scene = _stat(variant)
    scene.pop(missing)
    with pytest.raises(ValidationError, match=f"requires {missing}"):
        StatScene.model_validate(scene)


@pytest.mark.parametrize(
    ("value", "ok"),
    [("0%", True), ("62.5%", True), ("100%", True), ("101%", False), ("62", False), ("$50", False)],
)
def test_ring_needs_a_zero_to_hundred_percent_value(value: str, ok: bool) -> None:
    assert _valid(StatScene, _stat("ring", value=value)) is ok


@pytest.mark.parametrize(
    ("field", "count", "ok"),
    [
        *[("bars", 1, False), ("bars", 2, True), ("bars", 6, True), ("bars", 7, False)],
        *[("points", 2, False), ("points", 3, True), ("points", 8, True), ("points", 9, False)],
    ],
)
def test_series_length_bounds(field: str, count: int, ok: bool) -> None:
    items = [{"label": f"L{i}", "value": str(i)} for i in range(count)]
    variant = "bars" if field == "bars" else "line"
    assert _valid(StatScene, _stat(variant, **{field: items})) is ok


@pytest.mark.parametrize(("variant", "field"), [("bars", "bars"), ("line", "points")])
def test_series_labels_must_be_distinct_ignoring_case(variant: str, field: str) -> None:
    items = [{"label": "Rail", "value": "1"}, {"label": "RAIL", "value": "2"}]
    with pytest.raises(ValidationError, match="labels must be distinct"):
        StatScene.model_validate(
            _stat(variant, **{field: [*items, {"label": "Bus", "value": "3"}]})
        )


@pytest.mark.parametrize(
    ("variant", "extra"),
    [
        ("big_number", {"bars": [{"label": "A", "value": "1"}, {"label": "B", "value": "2"}]}),
        ("ring", {"points": [{"label": str(y), "value": "1"} for y in (1, 2, 3)]}),
        ("bars", {"value": "62%"}),
        ("line", {"context": "Context for another variant"}),
    ],
)
def test_variant_must_omit_other_variants_fields(variant: str, extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match=f"variant {variant} must omit {next(iter(extra))}"):
        StatScene.model_validate(_stat(variant, **extra))


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        *[("62%", True), ("1,240", True), ("$2.5bn", True), ("3.8 million", True), ("12.5k", True)],
        *[("about 60", False), ("62 %%", False), ("1e6", False), ("1,24", False), (62, False)],
    ],
)
def test_stat_value_pattern(value: object, ok: bool) -> None:
    assert _valid(StatScene, _stat(value=value)) is ok


@pytest.mark.parametrize(("count", "ok"), [(3, False), (4, True), (6, True), (7, False)])
def test_timeline_milestone_count_bounds(count: int, ok: bool) -> None:
    assert _valid(TimelineScene, _timeline(count)) is ok


@pytest.mark.parametrize(
    ("date", "ok"), [("Apr 1990", True), ("1969", True), ("Spring", False), ("x1" * 7, False)]
)
def test_timeline_date_must_contain_a_digit_and_fit(date: str, ok: bool) -> None:
    scene = _timeline()
    scene["milestones"][0]["date"] = date
    assert _valid(TimelineScene, scene) is ok


@pytest.mark.parametrize(
    ("index", "name"), [(0, "Reuters"), (1, "The Guardian"), (2, "the source")]
)
def test_stat_source_line_names_the_cited_record(index: int, name: str) -> None:
    sources = [WATER, POWER, {"title": "Unknown feed", "source": "somewhere-new"}]
    assert source_line(_stat(source_index=index), sources) == f"Source: {name}"


def test_timeline_source_line_lists_up_to_two_publications_and_steps_have_none() -> None:
    sources = [{"title": "A", "source": "wikipedia"}, {"title": "B", "source": "wikipedia"}]
    sources += [{"title": "C", "source": "google_news", "publisher": "AP News"}, POWER]
    assert source_line(_timeline(), sources) == "Source: Wikipedia and AP News"
    assert source_line(_timeline(), sources[:2]) == "Source: Wikipedia"
    assert source_line(_timeline(), []) is None
    assert source_line(_steps(), sources) is None


@pytest.fixture()
def reel(sample_caption_data: dict[str, Any]) -> dict[str, Any]:
    """The publishing fields an SVG Reel keeps from the caption fixture."""
    return {key: sample_caption_data[key] for key in ("caption", "hashtags", "x_post")}


def _check(raw: dict, kind: str = "stat", sources: list[dict] | None = None):
    return validate_svg_content(raw, kind=kind, sources=[WATER] if sources is None else sources)


@pytest.mark.parametrize(
    "context",
    [
        "Decline in a rare Texas shark species, per Chron",  # 2026-10-11 dry run
        "Rise in U.S. drinking water bills in a decade",
        "Drop in sea ice since 1979",
        "How far the index fell this year",
    ],
)
def test_ring_is_refused_for_a_change(context: str) -> None:
    with pytest.raises(ValidationError, match="ring shows a share of a whole"):
        StatScene.model_validate(_stat("ring", context=context))


def test_ring_still_takes_a_share_of_a_whole() -> None:
    assert StatScene.model_validate(_stat("ring")).variant == "ring"


def test_grounded_stat_scene_passes(reel: dict[str, Any]) -> None:
    content = _check(
        {
            **reel,
            "caption": "Water bills climbed fast.\nThey rose 62% in a decade.",
            "scene": _stat(),
        }
    )
    assert content.scene.value == "62%"
    assert set(content.model_dump()) == {"caption", "hashtags", "x_post", "scene"}


def test_hallucinated_number_is_rejected(reel: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"cited source text; not found there: 64\.") as error:
        _check({**reel, "scene": _stat(value="64%")})
    assert not isinstance(error.value, ValidationError)


def test_commentary_about_the_source_triggers_a_repair(reel: dict[str, Any]) -> None:
    scene = _stat(takeaway="Bills rose; the summary omits which cities.")
    with pytest.raises(ValueError, match=r'scene\.takeaway says "summary"') as error:
        _check(
            {
                **reel,
                "caption": "Water bills climbed fast.\nThey rose 62% in a decade.",
                "scene": scene,
            }
        )
    assert not isinstance(error.value, ValidationError)


def test_number_must_be_in_the_cited_source_not_just_any_source(reel: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"not found there: 64\."):
        _check({**reel, "scene": _stat(value="64%")}, sources=[WATER, POWER])
    content = _check({**reel, "scene": _stat(value="64%", source_index=1)}, sources=[WATER, POWER])
    assert content.scene.source_index == 1


@pytest.mark.parametrize("index", [1, 2])
def test_source_index_must_reference_a_supplied_record(reel: dict[str, Any], index: int) -> None:
    with pytest.raises(ValueError, match="source_index must reference a supplied source record"):
        _check({**reel, "scene": _stat(source_index=index)})


def test_caption_figures_must_be_in_evidence_but_links_and_tags_are_ignored(
    reel: dict[str, Any],
) -> None:
    links = " Read https://example.org/2024/report-7 #top10 #2026"
    grounded = {
        **reel,
        "caption": "Water bills climbed fast.\nThey rose 62% in a decade." + links,
        "scene": _stat(),
    }
    assert _check(grounded).caption.endswith("#2026")
    with pytest.raises(ValueError, match="caption may only use numbers") as error:
        _check({**grounded, "caption": "That is 62 for every 100 homes." + links})
    assert re.search(r"not found there: ([^.]+)\.", str(error.value)).group(1) == "100"


@pytest.mark.parametrize(
    ("scene", "kind"), [(_steps(), "stat"), (_stat(), "timeline"), (_timeline(), "steps")]
)
def test_scene_kind_must_match_the_pillar(reel: dict[str, Any], scene: dict, kind: str) -> None:
    with pytest.raises(ValueError, match=f'scene.kind must be "{kind}" for this pillar'):
        _check({**reel, "scene": scene}, kind=kind)


def test_steps_number_word_needs_evidence(reel: dict[str, Any]) -> None:
    scene = _steps()
    scene["steps"][0]["detail"] = "Your device creates two keys that belong together"
    with pytest.raises(ValueError, match=r"not found there: 2\."):
        _check({**reel, "scene": scene}, kind="steps", sources=[])
    scene["steps"][0]["detail"] = "Your device creates a key pair"
    assert _check({**reel, "scene": scene}, kind="steps", sources=[]).scene.kind == "steps"


def test_icon_names_are_not_scene_text(reel: dict[str, Any]) -> None:
    scene = _steps()
    for step in scene["steps"]:
        step["icon"] = "chart-column"
    texts = scene_texts(scene)
    assert "chart-column" not in texts
    assert _check({**reel, "scene": scene}, kind="steps", sources=[]).scene.steps[0].icon


def test_scene_too_long_for_the_layout_is_a_value_error(reel: dict[str, Any]) -> None:
    scene = _steps(
        6, hook=WIDE_HOOK, takeaway="WHEN MOM WAKES WARM MACHINES, MANY WORKERS WALK HOME"
    )
    for step in scene["steps"]:
        step["detail"] = "The browser asks which server holds the domain"
    assert _valid(StepsScene, scene)
    with pytest.raises(
        ValueError, match=r"scene does not fit the Reel layout: .*too long"
    ) as error:
        _check({**reel, "scene": scene}, kind="steps", sources=[])
    assert isinstance(error.value.__cause__, LayoutError)
    assert not isinstance(error.value, LayoutError)


def test_schema_and_grounding_errors_are_reported_together(reel: dict[str, Any]) -> None:
    with pytest.raises(ValueError) as error:
        _check({**reel, "scene": _stat(value="64%", headline="h" * 49)})
    message = str(error.value)
    assert "scene.stat.headline" in message
    assert "Also: every number and date in the scene" in message
    assert "not found there: 64" in message
    assert not isinstance(error.value, ValidationError)


@pytest.mark.parametrize(
    "field",
    ["image_prompts", "alt_texts", "slide_notes", "video_prompt", "audio_theme", "location_query"],
)
def test_photo_fields_are_rejected(reel: dict, sample_caption_data: dict, field: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _check({**reel, "scene": _stat(), field: sample_caption_data[field]})
