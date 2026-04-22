"""Tests for caption generation."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from src.content.caption import generate_caption


class TestGenerateCaption:
    @patch("src.content.caption.invoke_claude")
    def test_returns_all_required_fields(
        self,
        mock_claude: MagicMock,
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

    @patch("src.content.caption.invoke_claude")
    def test_passes_pillar_and_style_to_prompt(
        self,
        mock_claude: MagicMock,
        sample_pillar: dict[str, Any],
        sample_persona: dict[str, Any],
        sample_caption_data: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps(sample_caption_data)
        generate_caption("Test topic", sample_pillar, sample_persona)
        prompt_sent = mock_claude.call_args[0][1]
        assert sample_pillar["label"] in prompt_sent
        assert sample_pillar["image_style"] in prompt_sent
