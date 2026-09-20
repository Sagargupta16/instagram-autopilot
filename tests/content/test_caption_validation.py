"""Regression cases for malformed content before expensive media generation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.content.caption import generate_caption


@pytest.fixture(autouse=True)
def no_history():
    with patch("src.content.caption.load_recent_image_prompts", return_value=[]):
        yield


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("image_prompts", "abcde"),
        ("image_prompts", ["one", "two"]),
        ("image_prompts", ["one", "two", "three", "four", "five", "six"]),
        ("image_prompts", ["one", "two", "three", "four", "   "]),
        ("image_prompts", ["one", "two", "three", "four", 5]),
        ("image_prompts", ["one", "two", "three", "four", " ONE! "]),
        ("caption", " "),
        ("caption", "x" * 1801),
        ("hashtags", "#tag " * 100),
        ("hashtags", "travel food"),
        ("hashtags", " ".join(f"#tag{i}" for i in range(31))),
        ("audio_theme", "viral"),
        ("location_query", ["Paris"]),
        ("location_query", "null"),
        ("alt_texts", ["one"]),
        ("alt_texts", ["one", "two", "three", "four", " "]),
        ("slide_notes", ["same"] * 5),
        ("slide_notes", ["one", "two"]),
        ("x_post", "x" * 281),
        ("video_prompt", "x" * 401),
        ("alt_texts", ["one", "two", "three", "four", 5]),
        ("location_query", ""),
        ("caption", False),
        ("image_prompts", ["!!!", "two", "three", "four", "five"]),
    ],
)
def test_rejects_invalid_content_after_one_repair(
    field, bad_value, sample_caption_data, sample_pillar, sample_persona
):
    sample_caption_data[field] = bad_value
    with (
        patch(
            "src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)
        ) as model,
        pytest.raises(ValueError),
    ):
        generate_caption("Useful guide", sample_pillar, sample_persona)
    assert model.call_count == 2


@pytest.mark.parametrize("bad_response", ["not JSON", "[]", '{"caption": false}'])
def test_repairs_json_and_schema_once(
    bad_response, sample_caption_data, sample_pillar, sample_persona
):
    with patch(
        "src.content.caption.invoke_claude",
        side_effect=[bad_response, json.dumps(sample_caption_data)],
    ) as model:
        result = generate_caption("Useful guide", sample_pillar, sample_persona)
    assert result["alt_texts"] == sample_caption_data["alt_texts"]
    assert model.call_count == 2
    assert "repair" in model.call_args.args[1].lower()


def test_forwards_evidence_without_inventing_missing_metadata(
    sample_caption_data, sample_pillar, sample_persona
):
    sources = [
        {
            "title": "Packing a day bag",
            "source": "guardian",
            "url": "https://example.org/day-bag",
            "excerpt": "Pack a refillable bottle in an accessible pocket.",
        }
    ]
    with patch(
        "src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)
    ) as model:
        result = generate_caption(
            "A day bag checklist", sample_pillar, sample_persona, sources=sources
        )
    prompt = model.call_args.args[1]
    assert "https://example.org/day-bag" in prompt
    assert "refillable bottle" in prompt
    assert result["location_query"] is None
    assert "published_at" not in json.dumps(sources)


def test_transport_failure_is_not_retried(sample_pillar, sample_persona):
    with (
        patch("src.content.caption.invoke_claude", side_effect=RuntimeError("offline")) as model,
        pytest.raises(RuntimeError, match="offline"),
    ):
        generate_caption("Useful guide", sample_pillar, sample_persona)
    assert model.call_count == 1


@pytest.mark.parametrize(
    "bad_prompt",
    [
        "A mountain valley without tourists, dawn light.",
        "A poster with the text 'SAVE THIS', studio light.",
        "An infographic with labeled steps, white background.",
    ],
)
def test_rejects_diffusion_negation_and_text_requests(
    bad_prompt, sample_caption_data, sample_pillar, sample_persona
):
    sample_caption_data["image_prompts"][0] = bad_prompt
    with (
        patch("src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)),
        pytest.raises(ValueError),
    ):
        generate_caption("Useful guide", sample_pillar, sample_persona)


@pytest.mark.parametrize("theme", ["chill", "upbeat", "cinematic", "ambient", "energetic"])
def test_valid_response_preserves_themes_nullable_location_and_optional_notes(
    theme, sample_caption_data, sample_pillar, sample_persona
):
    sample_caption_data["audio_theme"] = theme
    sample_caption_data.pop("slide_notes")
    with patch(
        "src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)
    ) as model:
        result = generate_caption("Useful guide", sample_pillar, sample_persona)
    assert result["audio_theme"] == theme
    assert result["location_query"] is None
    assert len(result["alt_texts"]) == 5
    assert model.call_count == 1


@pytest.mark.parametrize(
    "field", ["caption", "image_prompts", "alt_texts", "audio_theme", "location_query"]
)
def test_missing_required_fields_fail_closed(
    field, sample_caption_data, sample_pillar, sample_persona
):
    sample_caption_data.pop(field)
    with (
        patch("src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)),
        pytest.raises(ValueError),
    ):
        generate_caption("Useful guide", sample_pillar, sample_persona)


@pytest.mark.parametrize("caption_length", [1798, 1800])
def test_combined_instagram_limit(
    caption_length, sample_caption_data, sample_pillar, sample_persona
):
    sample_caption_data["caption"] = "x" * caption_length
    sample_caption_data["hashtags"] = "#" + "a" * 199 + " #" + "b" * 198
    with patch("src.content.caption.invoke_claude", return_value=json.dumps(sample_caption_data)):
        if caption_length == 1798:
            result = generate_caption("Useful guide", sample_pillar, sample_persona)
            assert len(result["caption"] + "\n\n" + result["hashtags"]) == 2200
        else:
            with pytest.raises(ValueError):
                generate_caption("Useful guide", sample_pillar, sample_persona)
