"""GitHub search API for trending generative-AI repos (no auth, 60 req/hr)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import requests

from src.content.sources import records_or_titles, source_record

SEARCH_URL = "https://api.github.com/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "instagram-autopilot/0.5 (trends-fetcher)",
}


def fetch_trending(
    topic: str = "generative-ai", limit: int = 10, days: int = 14, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return recently-pushed repos, optionally retaining URLs and descriptions."""
    if limit <= 0:
        return []
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    query = f"topic:{topic} pushed:>{since} stars:>50"
    resp = requests.get(
        SEARCH_URL,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    results: list[dict[str, str]] = []
    for item in items[:limit]:
        name = item.get("name") or ""
        desc = (item.get("description") or "").strip()
        if name:
            results.append(
                source_record(
                    f"{name}: {desc}" if desc else name,
                    "github",
                    "technology",
                    url=item.get("html_url"),
                    updated_at=item.get("pushed_at"),
                    excerpt=desc,
                )
            )
    return records_or_titles(results, include_metadata)
