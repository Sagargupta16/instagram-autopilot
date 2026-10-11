"""Topic briefs for the animated SVG Reel formats need matching source evidence."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.content import topic

NO_NUMBER = {
    "title": "Scientists map a coral reef",
    "source": "guardian",
    "url": "https://example.org/2026/09/19/reef-42",
    "published_at": "2026-09-19",
    "excerpt": "Divers charted the reef by hand.",
}
WITH_NUMBER = {
    "title": "U.S. drinking water bills rose 62% in a decade",
    "source": "google_news",
    "publisher": "Reuters",
}
EARLY_DATES = {"title": "Space race", "excerpt": "Sputnik flew in 1957 and Gagarin in 1961."}
LATE_DATES = {"title": "Moon landings", "excerpt": "Apollo 11 landed in 1969; the last in 1972."}


def _pillar(kind: str | None) -> dict[str, Any]:
    base = {"id": "pillar", "label": "Pillar", "hashtags": ["#x"], "image_style": "editorial"}
    if kind is None:
        return {**base, "content_format": "carousel"}
    return {**base, "content_format": "svg_reel", "scene_kind": kind}


def _choice(indices: list[int], name: str = "A fresh angle") -> str:
    return json.dumps({"topic": name, "source_indices": indices})


@pytest.fixture(autouse=True)
def no_history():
    with patch("src.content.topic.load_posted_topics", return_value=[]):
        yield


@pytest.mark.parametrize("kind", ["stat", "timeline"])
def test_numeric_formats_fail_before_any_model_call_without_numbers(kind: str) -> None:
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[NO_NUMBER]),
        patch("src.content.topic.invoke_claude") as model,
        pytest.raises(ValueError, match=f"No source evidence with numbers or dates for a {kind}"),
    ):
        topic.generate_topic_brief(_pillar(kind), "stat")
    model.assert_not_called()


def test_numeric_format_fails_closed_when_trends_fail() -> None:
    with (
        patch("src.content.topic.fetch_trending_topics", side_effect=RuntimeError("down")),
        patch("src.content.topic.invoke_claude") as model,
        pytest.raises(ValueError, match="No source evidence"),
    ):
        topic.generate_topic_brief(_pillar("stat"), "stat")
    model.assert_not_called()


def test_stat_choice_without_a_number_is_repaired_once() -> None:
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[NO_NUMBER, WITH_NUMBER]),
        patch(
            "src.content.topic.invoke_claude",
            side_effect=[_choice([0], "Mapping a reef"), _choice([1], "Water bills rose")],
        ) as model,
    ):
        brief = topic.generate_topic_brief(_pillar("stat"), "stat")
    assert brief == {"topic": "Water bills rose", "sources": [WITH_NUMBER]}
    assert model.call_count == 2
    repair = model.call_args.args[1]
    assert "<repair>" in repair
    assert "a stat Reel needs a selected source" in repair


def test_stat_choice_without_a_number_fails_after_one_repair() -> None:
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[NO_NUMBER, WITH_NUMBER]),
        patch("src.content.topic.invoke_claude", return_value=_choice([0])) as model,
        pytest.raises(ValueError, match="a stat Reel needs"),
    ):
        topic.generate_topic_brief(_pillar("stat"), "stat")
    assert model.call_count == 2


@pytest.mark.parametrize("indices", [[], [0], [1], [0, 2]])
def test_timeline_rejects_selections_with_fewer_than_four_distinct_dates(
    indices: list[int],
) -> None:
    repeated = {"title": "Anniversaries", "excerpt": "1957, 1957 and 1961 again in 1961."}
    with (
        patch(
            "src.content.topic.fetch_trending_topics",
            return_value=[EARLY_DATES, LATE_DATES, repeated],
        ),
        patch("src.content.topic.invoke_claude", return_value=_choice(indices)) as model,
        pytest.raises(ValueError, match="at least four dates"),
    ):
        topic.generate_topic_brief(_pillar("timeline"), "timeline")
    assert model.call_count == 2


def test_timeline_repair_can_add_a_source_to_reach_four_dates() -> None:
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[EARLY_DATES, LATE_DATES]),
        patch(
            "src.content.topic.invoke_claude",
            side_effect=[_choice([1], "The space race"), _choice([0, 1], "The space race")],
        ) as model,
    ):
        brief = topic.generate_topic_brief(_pillar("timeline"), "timeline")
    assert brief["sources"] == [EARLY_DATES, LATE_DATES]
    assert model.call_count == 2


def _prompt(kind: str | None) -> str:
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[]),
        patch("src.content.topic.invoke_claude", return_value=_choice([])) as model,
    ):
        topic.generate_topic_brief(_pillar(kind), "explainer")
    return model.call_args.args[1]


def test_steps_prompt_uses_the_steps_brief() -> None:
    prompt = _prompt("steps")
    assert (topic.FORMATS_DIR / "steps.topic.txt").read_text(encoding="utf-8").strip() in prompt
    carousel = (topic.FORMATS_DIR / "carousel.topic.txt").read_text(encoding="utf-8").strip()
    assert carousel not in prompt


def test_carousel_prompt_uses_the_carousel_brief() -> None:
    prompt = _prompt(None)
    assert (topic.FORMATS_DIR / "carousel.topic.txt").read_text(encoding="utf-8").strip() in prompt
    for kind in ("steps", "stat", "timeline"):
        brief = (topic.FORMATS_DIR / f"{kind}.topic.txt").read_text(encoding="utf-8").strip()
        assert brief not in prompt
