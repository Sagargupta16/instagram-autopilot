"""Product Hunt Atom feed client (no auth required)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests

FEED_URL = "https://www.producthunt.com/feed"
HEADERS = {"User-Agent": "instagram-autopilot/0.5 (trends-fetcher)"}
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch_ai_launches(limit: int = 10) -> list[str]:
    """Return titles of trending AI-category Product Hunt launches."""
    resp = requests.get(
        FEED_URL,
        params={"category": "artificial-intelligence"},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    titles: list[str] = []
    for entry in root.findall(f"{ATOM_NS}entry")[:limit]:
        title_el = entry.find(f"{ATOM_NS}title")
        if title_el is None or not title_el.text:
            continue
        # strip HTML and collapse whitespace -- PH titles are usually clean
        clean = re.sub(r"<[^>]+>", "", title_el.text).strip()
        if clean:
            titles.append(clean)
    return titles
