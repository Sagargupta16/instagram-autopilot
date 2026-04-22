"""Tests for text generation (Bedrock calls mocked)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.generator.text import generate_caption, generate_topic


class TestGenerateTopic:
    @patch("src.generator.text.fetch_trending_topics", return_value=[])
    @patch("src.generator.text._invoke_bedrock")
    @patch("src.generator.text._save_posted_topic")
    @patch("src.generator.text._load_posted_topics", return_value=[])
    def test_returns_topic_string(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_bedrock: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_bedrock.return_value = json.dumps({"topic": "Why your brain lies to you about time"})
        topic = generate_topic(sample_pillar, "fact")
        assert topic == "Why your brain lies to you about time"

    @patch("src.generator.text.fetch_trending_topics", return_value=[])
    @patch("src.generator.text._invoke_bedrock")
    @patch("src.generator.text._save_posted_topic")
    @patch("src.generator.text._load_posted_topics", return_value=[])
    def test_saves_topic_after_generation(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_bedrock: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_bedrock.return_value = json.dumps({"topic": "The anchoring effect in negotiations"})
        generate_topic(sample_pillar, "tip")
        mock_save.assert_called_once_with("The anchoring effect in negotiations")

    @patch("src.generator.text.fetch_trending_topics", return_value=[])
    @patch("src.generator.text._invoke_bedrock")
    @patch("src.generator.text._save_posted_topic")
    @patch("src.generator.text._load_posted_topics", return_value=[])
    def test_raises_on_invalid_json(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_bedrock: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_bedrock.return_value = "not valid json"
        with pytest.raises(json.JSONDecodeError):
            generate_topic(sample_pillar, "fact")

    @patch(
        "src.generator.text.fetch_trending_topics",
        return_value=["GPT-6 leaks", "New Midjourney v7"],
    )
    @patch("src.generator.text._invoke_bedrock")
    @patch("src.generator.text._save_posted_topic")
    @patch("src.generator.text._load_posted_topics", return_value=[])
    def test_passes_trending_topics_to_prompt(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_bedrock: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_bedrock.return_value = json.dumps({"topic": "Midjourney v7 prompting tricks"})
        generate_topic(sample_pillar, "tip")
        prompt_sent = mock_bedrock.call_args[0][0]
        assert "GPT-6 leaks" in prompt_sent
        assert "New Midjourney v7" in prompt_sent

    @patch("src.generator.text.fetch_trending_topics", side_effect=RuntimeError("network down"))
    @patch("src.generator.text._invoke_bedrock")
    @patch("src.generator.text._save_posted_topic")
    @patch("src.generator.text._load_posted_topics", return_value=[])
    def test_degrades_gracefully_when_trends_fail(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_bedrock: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_bedrock.return_value = json.dumps({"topic": "fallback topic"})
        topic = generate_topic(sample_pillar, "tip")
        assert topic == "fallback topic"


class TestGenerateCaption:
    @patch("src.generator.text._invoke_bedrock")
    def test_returns_all_required_fields(
        self,
        mock_bedrock: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, str],
    ) -> None:
        mock_bedrock.return_value = json.dumps(sample_caption_data)
        result = generate_caption("Test topic", sample_pillar, sample_persona)
        assert "caption" in result
        assert "hashtags" in result
        assert "x_post" in result
        assert "image_prompts" in result
        assert len(result["image_prompts"]) == 5
        assert "video_prompt" in result

    @patch("src.generator.text._invoke_bedrock")
    def test_includes_pillar_and_style_in_prompt(
        self,
        mock_bedrock: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, str],
    ) -> None:
        mock_bedrock.return_value = json.dumps(sample_caption_data)
        generate_caption("Test topic", sample_pillar, sample_persona)
        prompt_sent = mock_bedrock.call_args[0][0]
        assert "Cognitive Biases" in prompt_sent
        assert "PHOTOREALISM" in prompt_sent
