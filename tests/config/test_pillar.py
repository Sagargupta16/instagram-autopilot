"""Tests for pillar config loading."""

from __future__ import annotations

import json

import pytest

from src.config.pillar import load_config


def test_load_config_returns_dict() -> None:
    config = load_config()
    assert isinstance(config, dict)


def test_load_config_has_required_top_level_keys() -> None:
    config = load_config()
    assert "persona" in config
    assert "pillars" in config
    assert "models" in config


def test_load_config_has_model_ids() -> None:
    config = load_config()
    assert "text" in config["models"]
    assert "image" in config["models"]
    assert "video" in config["models"]


def test_persona_has_required_fields() -> None:
    config = load_config()
    persona = config["persona"]
    assert "name" in persona
    assert "tone" in persona


def test_pillars_have_content_format() -> None:
    for pillar in load_config()["pillars"]:
        assert "id" in pillar
        assert "content_format" in pillar


@pytest.mark.parametrize(
    "field,value",
    [
        ("skip_probability", 2),
        ("post_probability", [0, 0, 0]),
        ("window_utc", {"start": "25:00", "end": "20:00"}),
        ("min_gap_minutes", -1),
    ],
)
def test_invalid_cadence_fails_before_service_calls(tmp_path, monkeypatch, field, value):
    import src.config.pillar as pillar

    config = load_config()
    config["cadence"][field] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(pillar, "CONFIG_PATH", path)
    with pytest.raises(ValueError):
        load_config()


def test_shipped_cadence_is_two_spaced_posts_a_day_at_most() -> None:
    cadence = load_config()["cadence"]
    assert cadence["max_posts_per_day"] == 2
    assert cadence["min_gap_minutes"] == 180
    assert cadence["post_probability"] == [0.05, 0.35, 0.60]
    assert len(cadence["post_probability"]) == cadence["max_posts_per_day"] + 1
    assert cadence["window_utc"] == {"start": "04:00", "end": "20:00"}
    assert cadence["schedule_buffer_minutes"] == 40


def test_shipped_pillars_are_the_five_svg_reel_formats() -> None:
    pillars = load_config()["pillars"]
    assert [(p["id"], p["weight"], p["scene_kind"]) for p in pillars] == [
        ("tech-explainer", 1.0, "steps"),
        ("cool-stats", 1.5, "stat"),
        ("history-timeline", 0.8, "timeline"),
        ("tech-versus", 1.0, "versus"),
        ("myth-vs-fact", 1.0, "myths"),
    ]
    for pillar in pillars:
        assert pillar["content_format"] == "svg_reel"
        assert pillar["audio_theme"] in {"chill", "upbeat", "cinematic"}


@pytest.mark.parametrize(
    ("content_format", "scene_kind"), [("svg_reel", None), ("carousel", "steps"), ("image", "stat")]
)
def test_scene_kind_must_match_content_format(tmp_path, monkeypatch, content_format, scene_kind):
    import src.config.pillar as pillar

    config = load_config()
    config["pillars"][0]["content_format"] = content_format
    config["pillars"][0].pop("scene_kind")
    if scene_kind is not None:
        config["pillars"][0]["scene_kind"] = scene_kind
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(pillar, "CONFIG_PATH", path)
    with pytest.raises(ValueError, match="svg_reel pillars need a scene_kind"):
        load_config()
