"""Product Hunt Atom feed client (no auth required)."""

from __future__ import annotations

import requests
from defusedxml import ElementTree as ET

from src.content.sources import records_or_titles, source_record

FEED_URL = "https://www.producthunt.com/feed"
HEADERS = {"User-Agent": "instagram-autopilot/0.5 (trends-fetcher)"}
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch_ai_launches(
    limit: int = 10, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return AI-category launches; retain provided summaries, not inferred claims."""
    if limit <= 0:
        return []
    resp = requests.get(
        FEED_URL,
        params={"category": "artificial-intelligence"},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    records: list[dict[str, str]] = []
    for entry in root.findall(f"{ATOM_NS}entry")[:limit]:
        title_el = entry.find(f"{ATOM_NS}title")
        if title_el is None or not title_el.text:
            continue
        links = entry.findall(f"{ATOM_NS}link")
        url = next(
            (link.get("href") for link in links if link.get("rel", "alternate") == "alternate"),
            None,
        )
        records.append(
            source_record(
                title_el.text,
                "producthunt",
                "technology",
                url=url,
                published_at=entry.findtext(f"{ATOM_NS}published"),
                updated_at=entry.findtext(f"{ATOM_NS}updated"),
                excerpt=entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content"),
            )
        )
    return records_or_titles(records, include_metadata)
