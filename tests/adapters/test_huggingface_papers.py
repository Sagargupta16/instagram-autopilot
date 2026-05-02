"""Tests for HuggingFace daily papers adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.adapters.huggingface_papers import fetch_daily_papers


class TestFetchDailyPapers:
    @patch("src.adapters.huggingface_papers.requests.get")
    def test_returns_paper_titles(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value=[
                    {"paper": {"title": "Scaling Laws for Neural Language Models"}},
                    {"paper": {"title": "DALL-E 3 technical report"}},
                ]
            ),
        )
        titles = fetch_daily_papers()
        assert titles == [
            "Scaling Laws for Neural Language Models",
            "DALL-E 3 technical report",
        ]

    @patch("src.adapters.huggingface_papers.requests.get")
    def test_respects_limit(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value=[{"paper": {"title": f"Paper {i}"}} for i in range(20)]),
        )
        titles = fetch_daily_papers(limit=3)
        assert len(titles) == 3

    @patch("src.adapters.huggingface_papers.requests.get")
    def test_skips_items_without_title(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value=[
                    {"paper": {"title": "Good one"}},
                    {"paper": {}},
                    {},
                ]
            ),
        )
        titles = fetch_daily_papers()
        assert titles == ["Good one"]
