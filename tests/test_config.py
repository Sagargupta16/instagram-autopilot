"""Tests for config loading and pillar scheduling."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from src.config import get_todays_pillar, load_config


class TestLoadConfig:
    def test_loads_valid_config(self) -> None:
        config = load_config()
        assert "persona" in config
        assert "pillars" in config
        assert "posting" in config
        assert "image_styles" in config

    def test_has_required_pillar_fields(self) -> None:
        config = load_config()
        for pillar in config["pillars"]:
            assert "id" in pillar
            assert "label" in pillar
            assert "days" in pillar
            assert "hashtags" in pillar
            assert len(pillar["days"]) > 0
            assert len(pillar["hashtags"]) > 0

    def test_has_image_style_per_pillar(self) -> None:
        config = load_config()
        for pillar in config["pillars"]:
            assert pillar["id"] in config["image_styles"]
            style = config["image_styles"][pillar["id"]]
            assert "bg_gradient" in style
            assert "accent" in style
            assert "text_color" in style

    def test_persona_has_required_fields(self) -> None:
        config = load_config()
        persona = config["persona"]
        assert "name" in persona
        assert "tone" in persona
        assert "cta_styles" in persona


class TestGetTodaysPillar:
    def test_returns_pillar_on_scheduled_day(self, sample_config: dict[str, Any]) -> None:
        with patch("src.config.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "Monday"
            mock_dt.timezone = __import__("datetime").timezone
            pillar = get_todays_pillar(sample_config)
            assert pillar is not None
            assert "monday" in pillar["days"]

    def test_returns_none_on_sunday(self, sample_config: dict[str, Any]) -> None:
        with patch("src.config.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "Sunday"
            mock_dt.timezone = __import__("datetime").timezone
            pillar = get_todays_pillar(sample_config)
            assert pillar is None

    def test_all_weekdays_have_pillars(self, sample_config: dict[str, Any]) -> None:
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        for day in weekdays:
            with patch("src.config.datetime") as mock_dt:
                mock_dt.now.return_value.strftime.return_value = day
                mock_dt.timezone = __import__("datetime").timezone
                pillar = get_todays_pillar(sample_config)
                assert pillar is not None, f"No pillar for {day}"
