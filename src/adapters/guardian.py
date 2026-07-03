"""Guardian Open Platform search API.

Uses api-key=`test` by default (shared dev quota); override with
settings.guardian_api_key once a real free-tier key is registered.
"""

from __future__ import annotations

import logging

import requests

from src.settings import settings

log = logging.getLogger(__name__)

_URL = "https://content.guardianapis.com/search"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def fetch_articles(section: str, limit: int = 10) -> list[str]:
    """Return up to `limit` recent Guardian article titles for the given section."""
    key = settings.guardian_api_key or "test"
    try:
        resp = requests.get(
            _URL,
            params={
                "api-key": key,
                "section": section,
                "order-by": "newest",
                "page-size": limit,
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
    return [r["webTitle"] for r in results if r.get("webTitle")][:limit]
