"""HuggingFace daily papers client (no auth required)."""

from __future__ import annotations

import requests

DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


def fetch_daily_papers(limit: int = 10) -> list[str]:
    """Return titles of trending AI papers curated by HuggingFace community."""
    resp = requests.get(DAILY_PAPERS_URL, timeout=10)
    resp.raise_for_status()
    items = resp.json()
    titles: list[str] = []
    for item in items[:limit]:
        paper = item.get("paper") or {}
        title = paper.get("title") or item.get("title")
        if title:
            titles.append(title.strip())
    return titles
