"""Tests for GitHub trending repos adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.github_trending import fetch_trending


class TestFetchTrending:
    @patch("src.adapters.github_trending.requests.get")
    def test_returns_name_description_strings(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value={
                    "items": [
                        {"name": "langflow", "description": "Build AI agents visually"},
                        {"name": "comfyui", "description": "Node-based diffusion UI"},
                    ]
                }
            ),
        )
        results = fetch_trending()
        assert results[0] == "langflow: Build AI agents visually"
        assert results[1] == "comfyui: Node-based diffusion UI"

    @patch("src.adapters.github_trending.requests.get")
    def test_uses_topic_filter(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"items": []}),
        )
        fetch_trending(topic="llm", limit=5, days=7)
        params = mock_get.call_args.kwargs["params"]
        assert "topic:llm" in params["q"]
        assert params["per_page"] == 5

    @patch("src.adapters.github_trending.requests.get")
    def test_handles_missing_description(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"items": [{"name": "mystery-repo", "description": None}]}),
        )
        results = fetch_trending()
        assert results == ["mystery-repo"]
