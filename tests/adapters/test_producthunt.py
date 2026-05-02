"""Tests for Product Hunt feed adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.producthunt import fetch_ai_launches

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Buda - Recruit AI agents to run your company</title>
    <link href="https://www.producthunt.com/posts/buda"/>
  </entry>
  <entry>
    <title>PromptKit - The prompt engineering IDE</title>
    <link href="https://www.producthunt.com/posts/promptkit"/>
  </entry>
</feed>
"""


class TestFetchAiLaunches:
    @patch("src.adapters.producthunt.requests.get")
    def test_parses_atom_entries(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            text=SAMPLE_ATOM,
        )
        titles = fetch_ai_launches()
        assert "Buda - Recruit AI agents to run your company" in titles
        assert "PromptKit - The prompt engineering IDE" in titles

    @patch("src.adapters.producthunt.requests.get")
    def test_filters_by_ai_category(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(raise_for_status=MagicMock(), text=SAMPLE_ATOM)
        fetch_ai_launches()
        params = mock_get.call_args.kwargs["params"]
        assert params["category"] == "artificial-intelligence"
