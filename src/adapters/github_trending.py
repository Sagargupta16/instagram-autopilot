"""GitHub search API for trending generative-AI repos (no auth, 60 req/hr)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import requests

SEARCH_URL = "https://api.github.com/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "instagram-autopilot/0.5 (trends-fetcher)",
}


def fetch_trending(topic: str = "generative-ai", limit: int = 10, days: int = 14) -> list[str]:
    """Return 'name: description' strings for top-starred recently-pushed repos."""
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
    results: list[str] = []
    for item in items:
        name = item.get("name") or ""
        desc = (item.get("description") or "").strip()
        if name and desc:
            results.append(f"{name}: {desc}")
        elif name:
            results.append(name)
    return results
