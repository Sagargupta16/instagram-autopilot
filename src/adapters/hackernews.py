"""Hacker News Algolia search API client (no auth required)."""

from __future__ import annotations

import requests

from src.content.sources import records_or_titles, source_record

SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def search_stories(
    query: str, limit: int = 5, min_points: int = 50, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return matching HN stories; scores are discovery signals, not claim evidence."""
    if limit <= 0:
        return []
    resp = requests.get(
        SEARCH_URL,
        params={
            "query": query,
            "tags": "story",
            "numericFilters": f"points>{min_points}",
            "hitsPerPage": limit,
        },
        timeout=10,
    )
    resp.raise_for_status()
    records = [
        source_record(
            hit["title"],
            "hackernews",
            "technology",
            url=hit.get("url"),
            published_at=hit.get("created_at"),
            excerpt=hit.get("story_text"),
        )
        for hit in resp.json().get("hits", [])
        if hit.get("title")
    ][:limit]
    return records_or_titles(records, include_metadata)
