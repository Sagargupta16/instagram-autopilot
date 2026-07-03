"""Tests for pillar config loading."""

from __future__ import annotations

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
