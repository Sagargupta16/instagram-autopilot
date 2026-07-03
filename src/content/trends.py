"""Fetch trending topics in parallel across wide-lifestyle + tech sources.

Grounds daily post ideas in current conversations instead of Claude's
training data alone. Degrades gracefully -- if a source fails, the rest
still work.

Sources (all no-auth or dev-tier):
    - HuggingFace daily papers (trending AI research)
    - Product Hunt AI category atom feed
    - GitHub search (generative-ai, llm)
    - Hacker News Algolia search
    - Wikipedia pageviews top-1000
    - Google News RSS per lifestyle+tech category
    - Guardian API per section
    - Lemmy hot posts per community

Reddit is intentionally excluded: GitHub Actions runner IPs are on
Reddit's anti-bot blocklist (403).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.adapters import (
    github_trending,
    google_news,
    guardian,
    hackernews,
    huggingface_papers,
    lemmy,
    producthunt,
    wikipedia,
)

log = logging.getLogger(__name__)

_CATEGORIES = ("travel", "food", "fitness", "entertainment", "technology")
_GUARDIAN_SECTIONS = ("lifestyle", "food", "travel", "fitness", "technology", "film")
_LEMMY_COMMUNITIES = ("technology", "food", "travel", "fitness")


def _tasks() -> list[tuple[str, tuple]]:
    tasks: list[tuple[str, tuple]] = [
        ("hf-daily", (huggingface_papers.fetch_daily_papers, 8)),
        ("ph-ai", (producthunt.fetch_ai_launches, 6)),
        ("gh-genai", (github_trending.fetch_trending, "generative-ai", 4)),
        ("gh-llm", (github_trending.fetch_trending, "llm", 4)),
        ("hn-ai", (hackernews.search_stories, "artificial intelligence", 4)),
        ("wiki-top", (wikipedia.fetch_top_articles, 15)),
    ]
    tasks.extend((f"news-{c}", (google_news.fetch_headlines, c, 4)) for c in _CATEGORIES)
    tasks.extend((f"guardian-{s}", (guardian.fetch_articles, s, 4)) for s in _GUARDIAN_SECTIONS)
    tasks.extend((f"lemmy-{c}", (lemmy.fetch_hot_posts, c, 4)) for c in _LEMMY_COMMUNITIES)
    return tasks


def fetch_trending_topics(limit: int = 30) -> list[str]:
    """Return up to `limit` trending headlines, deduplicated."""
    tasks = _tasks()
    results: list[str] = []
    with ThreadPoolExecutor(max_workers=min(16, len(tasks))) as pool:
        futures = {pool.submit(fn, *args): name for name, (fn, *args) in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as e:
                log.warning("Trend source %s failed: %s", name, e)

    seen: set[str] = set()
    deduped = [t for t in results if not (t in seen or seen.add(t))]

    log.info("Fetched %d trending topics from %d sources", len(deduped), len(tasks))
    return deduped[:limit]
