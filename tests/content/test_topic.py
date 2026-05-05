"""Tests for topic generation (trends + Bedrock mocked)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.content.topic import generate_topic


class TestGenerateTopic:
    @patch("src.content.topic.fetch_trending_topics", return_value=[])
    @patch("src.content.topic.invoke_claude")
    @patch("src.content.topic.load_posted_topics", return_value=[])
    def test_returns_topic_string(
        self,
        mock_load: MagicMock,
        mock_claude: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps({"topic": "Why Midjourney loves symmetry"})
        assert generate_topic(sample_pillar, "tip") == "Why Midjourney loves symmetry"

    @patch("src.content.topic.fetch_trending_topics", return_value=[])
    @patch("src.content.topic.invoke_claude")
    @patch("src.content.topic.load_posted_topics", return_value=[])
    def test_raises_on_invalid_json(
        self,
        mock_load: MagicMock,
        mock_claude: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_claude.return_value = "not valid json"
        with pytest.raises(json.JSONDecodeError):
            generate_topic(sample_pillar, "tip")

    @patch(
        "src.content.topic.fetch_trending_topics",
        return_value=["GPT-6 leaks", "New Midjourney v7"],
    )
    @patch("src.content.topic.invoke_claude")
    @patch("src.content.topic.load_posted_topics", return_value=[])
    def test_passes_trending_topics_to_prompt(
        self,
        mock_load: MagicMock,
        mock_claude: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps({"topic": "Midjourney v7"})
        generate_topic(sample_pillar, "tip")
        prompt_sent = mock_claude.call_args[0][1]
        assert "GPT-6 leaks" in prompt_sent
        assert "New Midjourney v7" in prompt_sent

    @patch("src.content.topic.fetch_trending_topics", side_effect=RuntimeError("down"))
    @patch("src.content.topic.invoke_claude")
    @patch("src.content.topic.load_posted_topics", return_value=[])
    def test_degrades_gracefully_when_trends_fail(
        self,
        mock_load: MagicMock,
        mock_claude: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps({"topic": "fallback"})
        assert generate_topic(sample_pillar, "tip") == "fallback"

    @patch("src.content.topic.fetch_trending_topics", return_value=[])
    @patch("src.content.topic.invoke_claude")
    @patch(
        "src.content.topic.load_posted_topics",
        return_value=["old topic 1", "old topic 2"],
    )
    def test_passes_posted_history_to_prompt(
        self,
        mock_load: MagicMock,
        mock_claude: MagicMock,
        mock_trends: MagicMock,
        sample_pillar: dict[str, Any],
    ) -> None:
        mock_claude.return_value = json.dumps({"topic": "new topic"})
        generate_topic(sample_pillar, "tip")
        prompt_sent = mock_claude.call_args[0][1]
        assert "old topic 1" in prompt_sent
        assert "old topic 2" in prompt_sent
