"""Tests for trends aggregator."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.content import trends
from src.content.trends import fetch_trending_topics


@pytest.fixture(autouse=True)
def all_providers_mocked(monkeypatch):
    for module, function in (
        (trends.huggingface_papers, "fetch_daily_papers"),
        (trends.producthunt, "fetch_ai_launches"),
        (trends.github_trending, "fetch_trending"),
        (trends.hackernews, "search_stories"),
        (trends.wikipedia, "fetch_top_articles"),
        (trends.google_news, "fetch_headlines"),
        (trends.guardian, "fetch_articles"),
        (trends.lemmy, "fetch_hot_posts"),
    ):
        monkeypatch.setattr(module, function, lambda *args, **kwargs: [])


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


def test_selection_is_balanced_independent_of_completion_order():
    with (
        patch.object(
            trends.huggingface_papers, "fetch_daily_papers", return_value=["A1", "A2", "A3"]
        ),
        patch.object(trends.producthunt, "fetch_ai_launches", return_value=["B1", "B2", "B3"]),
        patch.object(trends.github_trending, "fetch_trending", return_value=["C1", "C2", "C3"]),
        patch.object(trends, "as_completed", side_effect=lambda futures: list(futures)),
    ):
        forward = fetch_trending_topics(limit=3)
        with patch.object(trends, "as_completed", side_effect=lambda futures: list(futures)[::-1]):
            reverse = fetch_trending_topics(limit=3)
    assert forward == reverse == ["A1", "B1", "C1"]


def test_travel_uses_relevant_sources_and_preserves_evidence():
    source = {
        "title": "Plan a train journey",
        "source": "google_news",
        "category": "travel",
        "url": "https://example.org/train",
        "published_at": "2026-09-19",
        "excerpt": "Compare connections before booking.",
    }
    with (
        patch.object(trends.google_news, "fetch_headlines", return_value=[source]) as news,
        patch.object(
            trends.guardian, "fetch_articles", return_value=["Walking in Kyoto"]
        ) as guardian,
        patch.object(trends.huggingface_papers, "fetch_daily_papers") as papers,
        patch.object(
            trends.wikipedia, "fetch_top_articles", return_value=["Celebrity scandal"]
        ) as wiki,
    ):
        result = fetch_trending_topics(
            limit=3, pillar={"category": "travel"}, include_metadata=True
        )
    assert result[0] == source
    assert any(record["title"] == "Walking in Kyoto" for record in result)
    assert news.call_args.args[0] == "travel"
    assert guardian.call_args.args[0] == "travel"
    papers.assert_not_called()
    wiki.assert_not_called()


def test_unknown_pillar_uses_evergreen_instead_of_unrelated_feeds():
    assert fetch_trending_topics(pillar={"category": "unknown"}) == []


def test_normalized_headlines_deduplicate():
    with (
        patch.object(trends.huggingface_papers, "fetch_daily_papers", return_value=["Café tools"]),
        patch.object(trends.producthunt, "fetch_ai_launches", return_value=[" CAFE\u0301 TOOLS! "]),
    ):
        assert fetch_trending_topics() == ["Café tools"]


def test_zero_limit_does_not_fetch():
    with patch.object(trends.huggingface_papers, "fetch_daily_papers") as papers:
        assert fetch_trending_topics(limit=0) == []
    papers.assert_not_called()


def test_malformed_provider_output_does_not_discard_other_sources():
    with (
        patch.object(trends.huggingface_papers, "fetch_daily_papers", return_value=None),
        patch.object(trends.producthunt, "fetch_ai_launches", return_value=["A useful tool"]),
    ):
        assert fetch_trending_topics() == ["A useful tool"]
