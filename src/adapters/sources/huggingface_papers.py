"""HuggingFace daily papers client (no auth required)."""

from __future__ import annotations

from urllib.parse import quote

import requests

from src.content.sources import records_or_titles, source_record

DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


def fetch_daily_papers(
    limit: int = 10, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return curated AI papers with optional abstract and publication evidence."""
    if limit <= 0:
        return []
    resp = requests.get(DAILY_PAPERS_URL, timeout=10)
    resp.raise_for_status()
    items = resp.json()
    records: list[dict[str, str]] = []
    for item in items[:limit]:
        paper = item.get("paper") or {}
        title = paper.get("title") or item.get("title")
        if title:
            paper_id = paper.get("id")
            url = f"https://huggingface.co/papers/{quote(paper_id, safe='')}" if paper_id else None
            records.append(
                source_record(
                    title,
                    "huggingface",
                    "technology",
                    url=url,
                    published_at=paper.get("publishedAt"),
                    excerpt=paper.get("summary"),
                )
            )
    return records_or_titles(records, include_metadata)
