"""Tests for pillar config loading and today's-pillar routing."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from src.pillar import get_todays_pillar, load_config


class TestLoadConfig:
    def test_loads_valid_config(self) -> None:
        config = load_config()
        assert "persona" in config
        assert "pillars" in config
        assert "posting" in config
        assert "models" in config

    def test_has_required_pillar_fields(self) -> None:
        config = load_config()
        for pillar in config["pillars"]:
            assert "id" in pillar
            assert "label" in pillar
            assert "days" in pillar
            assert "hashtags" in pillar
            assert "image_style" in pillar
            assert "content_format" in pillar

    def test_has_model_config(self) -> None:
        config = load_config()
        assert "text" in config["models"]
        assert "image" in config["models"]
        assert "video" in config["models"]

    def test_persona_has_required_fields(self) -> None:
        config = load_config()
        persona = config["persona"]
        assert "name" in persona
        assert "tone" in persona
        assert "cta_styles" in persona


class TestGetTodaysPillar:
    def test_returns_pillar_on_scheduled_day(self, sample_config: dict[str, Any]) -> None:
        with patch("src.pillar.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "Monday"
            mock_dt.UTC = __import__("datetime").UTC
            pillar = get_todays_pillar(sample_config)
            assert pillar is not None
            assert "monday" in pillar["days"]

    def test_returns_none_when_no_pillar_scheduled(self) -> None:
        config = {"pillars": [{"id": "test", "days": ["monday"]}]}
        with patch("src.pillar.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "Tuesday"
            mock_dt.UTC = __import__("datetime").UTC
            pillar = get_todays_pillar(config)
            assert pillar is None

    def test_all_days_have_pillars(self, sample_config: dict[str, Any]) -> None:
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            with patch("src.pillar.datetime") as mock_dt:
                mock_dt.now.return_value.strftime.return_value = day
                mock_dt.UTC = __import__("datetime").UTC
                pillar = get_todays_pillar(sample_config)
                assert pillar is not None, f"No pillar for {day}"
