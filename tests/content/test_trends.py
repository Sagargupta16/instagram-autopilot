"""Tests for trends aggregator."""

from __future__ import annotations

from unittest.mock import patch

from src.content.trends import fetch_trending_topics


class TestFetchTrendingTopics:
    def test_aggregates_all_sources_and_dedupes(self) -> None:
        with (
            patch(
                "src.content.trends.huggingface_papers.fetch_daily_papers",
                return_value=["Paper A", "Paper B"],
            ),
            patch(
                "src.content.trends.producthunt.fetch_ai_launches",
                return_value=["Tool X", "Paper A"],  # duplicate to test dedup
            ),
            patch(
                "src.content.trends.github_trending.fetch_trending",
                return_value=["repo: cool"],
            ),
            patch(
                "src.content.trends.hackernews.search_stories",
                return_value=["HN item"],
            ),
        ):
            result = fetch_trending_topics(limit=50)
        assert "Paper A" in result
        assert "Tool X" in result
        assert "repo: cool" in result
        assert "HN item" in result
        # dedup: "Paper A" appears only once
        assert result.count("Paper A") == 1

    def test_failing_source_does_not_break_others(self) -> None:
        with (
            patch(
                "src.content.trends.huggingface_papers.fetch_daily_papers",
                side_effect=RuntimeError("down"),
            ),
            patch(
                "src.content.trends.producthunt.fetch_ai_launches",
                return_value=["Tool X"],
            ),
            patch(
                "src.content.trends.github_trending.fetch_trending",
                return_value=[],
            ),
            patch("src.content.trends.hackernews.search_stories", return_value=[]),
        ):
            result = fetch_trending_topics()
        assert "Tool X" in result

    def test_respects_limit(self) -> None:
        with (
            patch(
                "src.content.trends.huggingface_papers.fetch_daily_papers",
                return_value=[f"paper-{i}" for i in range(50)],
            ),
            patch("src.content.trends.producthunt.fetch_ai_launches", return_value=[]),
            patch("src.content.trends.github_trending.fetch_trending", return_value=[]),
            patch("src.content.trends.hackernews.search_stories", return_value=[]),
        ):
            result = fetch_trending_topics(limit=5)
        assert len(result) == 5
