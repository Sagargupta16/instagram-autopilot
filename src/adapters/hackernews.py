"""Hacker News Algolia search API client (no auth required)."""

from __future__ import annotations

import requests

SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def search_stories(query: str, limit: int = 5, min_points: int = 50) -> list[str]:
    """Return titles of top HN stories matching a query."""
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
    return [hit["title"] for hit in resp.json().get("hits", []) if hit.get("title")]
