"""Tests for pillar config loading."""

from __future__ import annotations

import json

import pytest

from src.pillar import load_config


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
    import src.pillar as pillar

    config = load_config()
    config["cadence"][field] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(pillar, "CONFIG_PATH", path)
    with pytest.raises(ValueError):
        load_config()
