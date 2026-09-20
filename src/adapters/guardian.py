"""Guardian Open Platform search API.

Uses api-key=`test` by default (shared dev quota); override with
settings.guardian_api_key once a real free-tier key is registered.
"""

from __future__ import annotations

import logging

import requests

from src.content.sources import records_or_titles, source_record
from src.settings import settings

log = logging.getLogger(__name__)

_URL = "https://content.guardianapis.com/search"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def fetch_articles(
    section: str, limit: int = 10, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return Guardian headlines with optional original URL, date, and trail text."""
    if limit <= 0:
        return []
    key = settings.guardian_api_key or "test"
    try:
        resp = requests.get(
            _URL,
            params={
                "api-key": key,
                "section": "lifeandstyle" if section in {"fitness", "lifestyle"} else section,
                **({"q": "fitness OR exercise"} if section == "fitness" else {}),
                "order-by": "newest",
                "page-size": limit,
                "show-fields": "trailText",
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Guardian fetch (%s) failed: %s", section, e)
        return []
    if not resp.ok:
        log.warning("Guardian (%s) HTTP %s", section, resp.status_code)
        return []
    results = resp.json().get("response", {}).get("results", [])
    records = [
        source_record(
            result["webTitle"],
            "guardian",
            section,
            url=result.get("webUrl"),
            published_at=result.get("webPublicationDate"),
            excerpt=(result.get("fields") or {}).get("trailText"),
        )
        for result in results
        if result.get("webTitle")
    ][:limit]
    return records_or_titles(records, include_metadata)
