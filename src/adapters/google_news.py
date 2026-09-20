"""Google News RSS search (no auth, per-category).

Uses defusedxml -- stdlib xml.etree is vulnerable to XXE + billion-laughs
on untrusted input (RSS is untrusted).
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import requests
from defusedxml import ElementTree as ET

from src.content.sources import records_or_titles, source_record

log = logging.getLogger(__name__)

_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def fetch_headlines(
    category: str, limit: int = 10, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return category headlines, optionally with the evidence supplied by RSS."""
    if limit <= 0:
        return []
    try:
        resp = requests.get(
            _URL.format(q=quote(category)),
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Google News fetch (%s) failed: %s", category, e)
        return []
    if not resp.ok:
        log.warning("Google News (%s) HTTP %s", category, resp.status_code)
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        log.warning("Google News (%s) invalid XML: %s", category, e)
        return []
    records: list[dict[str, str]] = []
    for item in root.iterfind(".//item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            records.append(
                source_record(
                    title_el.text,
                    "google_news",
                    category,
                    url=item.findtext("link"),
                    published_at=item.findtext("pubDate"),
                    excerpt=item.findtext("description"),
                )
            )
        if len(records) >= limit:
            break
    return records_or_titles(records, include_metadata)
