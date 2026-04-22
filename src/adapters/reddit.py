"""Reddit public JSON API client (no auth required for read-only)."""

from __future__ import annotations

import requests

TOP_URL = "https://www.reddit.com/r/{subreddit}/top.json"
HEADERS = {"User-Agent": "instagram-autopilot/0.5 (trends-fetcher)"}


def fetch_top(subreddit: str, limit: int = 5, timeframe: str = "week") -> list[str]:
    """Return titles of top posts from a subreddit in the given timeframe."""
    resp = requests.get(
        TOP_URL.format(subreddit=subreddit),
        params={"t": timeframe, "limit": limit},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    children = resp.json().get("data", {}).get("children", [])
    return [c["data"]["title"] for c in children if c.get("data", {}).get("title")]
