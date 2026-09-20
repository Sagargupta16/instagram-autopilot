"""Pillar-relevant discovery with deterministic round-robin source selection."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import zip_longest
from typing import Any

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
from src.content.sources import normalize_topic, records_or_titles, source_record

log = logging.getLogger(__name__)

_CATEGORIES = ("travel", "food", "fitness", "entertainment", "technology", "lifestyle")
_SECTIONS = {"entertainment": "film", "lifestyle": "lifestyle"}
_LEMMY = {"travel", "food", "fitness", "technology"}


def _pillar_category(pillar: dict[str, Any]) -> str:
    for field in ("category", "label", "id"):
        value = str(pillar.get(field, "")).casefold()
        if value == "tech" or value.startswith("tech-"):
            return "technology"
        for category in _CATEGORIES:
            if value == category or value.startswith(f"{category}-"):
                return category
    return "unknown"


def _tasks(category: str | None = None) -> list[tuple[str, tuple]]:
    tasks: list[tuple[str, tuple]] = []
    if category is None or category == "technology":
        tasks.extend(
            [
                ("huggingface", (huggingface_papers.fetch_daily_papers, 8)),
                ("producthunt", (producthunt.fetch_ai_launches, 6)),
                ("github", (github_trending.fetch_trending, "generative-ai", 4)),
                ("github", (github_trending.fetch_trending, "llm", 4)),
                ("hackernews", (hackernews.search_stories, "artificial intelligence", 4)),
            ]
        )
    # The pageview feed has no category evidence. Keep it for legacy broad discovery only.
    if category is None:
        tasks.append(("wikipedia", (wikipedia.fetch_top_articles, 15)))
    categories = _CATEGORIES if category is None else (category,)
    for value in categories:
        if value not in _CATEGORIES:
            continue
        tasks.extend(
            [
                ("google_news", (google_news.fetch_headlines, value, 4)),
                ("guardian", (guardian.fetch_articles, _SECTIONS.get(value, value), 4)),
            ]
        )
        if value in _LEMMY:
            tasks.append(("lemmy", (lemmy.fetch_hot_posts, value, 4)))
    return tasks


def _collect(tasks: list[tuple[str, tuple]]) -> dict[int, list]:
    results: dict[int, list] = {}
    with ThreadPoolExecutor(max_workers=min(16, len(tasks))) as pool:
        futures = {
            pool.submit(function, *args, include_metadata=True): index
            for index, (_, (function, *args)) in enumerate(tasks)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                records = future.result()
                if not isinstance(records, list):
                    raise ValueError("source response must be a list")
                results[index] = records
            except Exception as error:
                log.warning("Trend source %s failed: %s", tasks[index][0], error)
    return results


def _balanced_records(
    tasks: list[tuple[str, tuple]], results: dict[int, list], category: str | None, limit: int
) -> list[dict[str, str]]:
    providers: dict[str, list[dict[str, str]]] = {}
    for index, (provider, _) in enumerate(tasks):
        for item in results.get(index, []):
            if isinstance(item, str):
                record = source_record(item, provider, category or "general")
            elif isinstance(item, dict) and isinstance(item.get("title"), str):
                record = dict(item)
            else:
                continue
            if record["title"].strip():
                providers.setdefault(provider, []).append(record)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for round_items in zip_longest(*providers.values()):
        for record in round_items:
            if record is None:
                continue
            key = normalize_topic(record["title"])
            if key and key not in seen:
                seen.add(key)
                selected.append(record)
                if len(selected) == limit:
                    return selected
    return selected


def fetch_trending_topics(
    limit: int = 30, *, pillar: dict[str, Any] | None = None, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Keep title-only compatibility; opt into original evidence for topic briefs."""
    if limit <= 0:
        return []
    category = _pillar_category(pillar) if pillar is not None else None
    tasks = _tasks(category)
    if not tasks:
        return []
    selected = _balanced_records(tasks, _collect(tasks), category, limit)
    log.info("Selected %d discovery signals across %d provider tasks", len(selected), len(tasks))
    return records_or_titles(selected, include_metadata)
