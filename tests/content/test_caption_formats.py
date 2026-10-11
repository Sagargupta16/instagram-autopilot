"""Caption generation for SVG Reel pillars: format rules, grounding and one bounded repair."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.content import caption
from src.content.caption import generate_caption

EVIDENCE = [
    {
        "title": "U.S. drinking water bills rose 62% in a decade",
        "source": "google_news",
        "publisher": "Reuters",
        "url": "https://example.org/2025/water",
    }
]
STAT_PILLAR = {
    "id": "cool-stats",
    "label": "Cool Stats",
    "category": "stats",
    "content_format": "svg_reel",
    "scene_kind": "stat",
    "hashtags": ["#data", "#statistics"],
    "image_style": "documentary still life",
}


def _reel(value: str) -> str:
    return json.dumps(
        {
            "caption": f"U.S. drinking water bills rose {value} in a decade.",
            "hashtags": "#data #water",
            "x_post": "Water bills keep climbing.",
            "scene": {
                "kind": "stat",
                "variant": "big_number",
                "headline": "Water bills rose fast",
                "value": value,
                "context": "Rise in U.S. drinking water bills in a decade",
                "takeaway": "Bills grew faster than most households expect.",
                "source_index": 0,
            },
        }
    )


@pytest.fixture(autouse=True)
def no_history():
    with patch("src.content.caption.load_recent_image_prompts", return_value=[]) as history:
        yield history


def _stat_rules() -> str:
    return (caption.FORMATS_DIR / "stat.scene.txt").read_text(encoding="utf-8").strip()


def test_grounded_stat_reel_is_returned_after_one_call(
    sample_persona: dict[str, Any], no_history
) -> None:
    with patch("src.content.caption.invoke_claude", return_value=_reel("62%")) as model:
        result = generate_caption("Water bills", STAT_PILLAR, sample_persona, sources=EVIDENCE)
    assert model.call_count == 1
    prompt = model.call_args.args[1]
    assert _stat_rules() in prompt
    assert "<animated_reel>" in prompt
    assert "U.S. drinking water bills rose 62% in a decade" in prompt
    assert set(result) == {"caption", "hashtags", "x_post", "scene"}
    assert result["scene"]["value"] == "62%"
    no_history.assert_not_called()


def test_ungrounded_number_gets_exactly_one_repair(sample_persona: dict[str, Any]) -> None:
    with patch(
        "src.content.caption.invoke_claude", side_effect=[_reel("64%"), _reel("62%")]
    ) as model:
        result = generate_caption("Water bills", STAT_PILLAR, sample_persona, sources=EVIDENCE)
    assert model.call_count == 2
    first, repair = (call.args[1] for call in model.call_args_list)
    assert "repair" not in first.lower()
    assert "repair" in repair.lower()
    assert "not found there: 64" in repair
    assert _stat_rules() in repair
    shown = {key: value for key, value in result["scene"].items() if value is not None}
    assert shown == json.loads(_reel("62%"))["scene"]


def test_second_ungrounded_response_raises(sample_persona: dict[str, Any]) -> None:
    with (
        patch("src.content.caption.invoke_claude", return_value=_reel("64%")) as model,
        pytest.raises(ValueError, match="not found there: 64"),
    ):
        generate_caption("Water bills", STAT_PILLAR, sample_persona, sources=EVIDENCE)
    assert model.call_count == 2


def test_svg_reel_without_sources_cannot_show_a_stat(sample_persona: dict[str, Any]) -> None:
    with (
        patch("src.content.caption.invoke_claude", return_value=_reel("62%")) as model,
        pytest.raises(ValueError, match="source_index must reference"),
    ):
        generate_caption("Water bills", STAT_PILLAR, sample_persona)
    assert model.call_count == 2


def test_carousel_prompt_has_no_animated_reel_rules(
    sample_caption_data: dict[str, Any],
    sample_pillar: dict[str, Any],
    sample_persona: dict[str, Any],
) -> None:
    with patch(
        "src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)
    ) as model:
        result = generate_caption("Useful guide", sample_pillar, sample_persona)
    assert "<animated_reel>" not in model.call_args.args[1]
    assert "scene" not in result
    assert len(result["image_prompts"]) == 5
