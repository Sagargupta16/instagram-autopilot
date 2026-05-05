"""Tests for caption generation."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from src.content.caption import generate_caption


class TestGenerateCaption:
    @patch("src.content.caption.load_recent_image_prompts", return_value=[])
    @patch("src.content.caption.invoke_claude")
    def test_returns_all_required_fields(
        self,
        mock_claude: MagicMock,
        mock_recent: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps(sample_caption_data)
        result = generate_caption("Test topic", sample_pillar, sample_persona)
        assert "caption" in result
        assert "hashtags" in result
        assert "x_post" in result
        assert "image_prompts" in result
        assert len(result["image_prompts"]) == 5
        assert "video_prompt" in result

    @patch("src.content.caption.load_recent_image_prompts", return_value=[])
    @patch("src.content.caption.invoke_claude")
    def test_passes_topic_and_pillar_to_prompt(
        self,
        mock_claude: MagicMock,
        mock_recent: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps(sample_caption_data)
        generate_caption("Test topic xyz", sample_pillar, sample_persona)
        prompt_sent = mock_claude.call_args[0][1]
        assert "Test topic xyz" in prompt_sent
        assert sample_pillar["label"] in prompt_sent

    @patch(
        "src.content.caption.load_recent_image_prompts",
        return_value=[
            "A woman in a Tokyo cafe leaning over her laptop, window light",
            "Close-up of hands typing on a mechanical keyboard, warm light",
        ],
    )
    @patch("src.content.caption.invoke_claude")
    def test_injects_recent_scenes_into_prompt(
        self,
        mock_claude: MagicMock,
        mock_recent: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps(sample_caption_data)
        generate_caption("Some topic", sample_pillar, sample_persona)
        prompt_sent = mock_claude.call_args[0][1]
        assert "Tokyo cafe" in prompt_sent
        assert "mechanical keyboard" in prompt_sent

    @patch("src.content.caption.load_recent_image_prompts", return_value=[])
    @patch("src.content.caption.invoke_claude")
    def test_passes_style_hint_from_pillar(
        self,
        mock_claude: MagicMock,
        mock_recent: MagicMock,
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, Any],
    ) -> None:
        pillar = {
            "id": "x",
            "label": "X",
            "days": [],
            "hashtags": [],
            "image_style": "Magnum Photos feel",
            "content_format": "carousel",
        }
        mock_claude.return_value = json.dumps(sample_caption_data)
        generate_caption("t", pillar, sample_persona)
        prompt_sent = mock_claude.call_args[0][1]
        assert "Magnum Photos feel" in prompt_sent
