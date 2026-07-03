"""Meta Graph /pages/search -- resolve a text query to a Place-tagged Page ID.

Composio has no Places search action and no Graph passthrough (as of
2026-07-03), so we call Meta directly. Filters response to Pages with
lat/lng populated -- otherwise Instagram rejects location_id with
INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID at publish time.

Cache hits at assets/cache/places.json with 30-day TTL; invalidate on
publish-time INVALID_LOCATION_ID (caller responsibility).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from src.settings import settings

log = logging.getLogger(__name__)

CACHE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "cache" / "places.json"
)
CACHE_TTL_DAYS = 30
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        log.warning("places cache corrupt, resetting")
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _is_fresh(entry: dict) -> bool:
    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
    except (KeyError, ValueError):
        return False
    return datetime.now(UTC) - cached_at < timedelta(days=CACHE_TTL_DAYS)


def resolve_location_id(query: str) -> str | None:
    """Return a Facebook Page ID with location data matching `query`, or None."""
    if not query or not settings.meta_user_access_token:
        return None
    cache = _load_cache()
    if query in cache and _is_fresh(cache[query]):
        return cache[query]["page_id"]
    version = settings.meta_graph_api_version
    url = f"https://graph.facebook.com/{version}/pages/search"
    try:
        resp = requests.get(
            url,
            params={
                "q": query,
                "fields": "id,name,location",
                "access_token": settings.meta_user_access_token,
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Places search (%s) network error: %s", query, e)
        return None
    if not resp.ok:
        log.warning(
            "Places search (%s) HTTP %s: %s", query, resp.status_code, resp.text[:200]
        )
        return None
    for page in resp.json().get("data", []):
        loc = page.get("location") or {}
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            page_id = str(page["id"])
            cache[query] = {
                "page_id": page_id,
                "cached_at": datetime.now(UTC).isoformat(),
            }
            _save_cache(cache)
            return page_id
    log.info("Places search (%s) returned no lat/lng results", query)
    return None


def invalidate(query: str) -> None:
    """Drop a query from the cache -- caller after INVALID_LOCATION_ID publish error."""
    cache = _load_cache()
    if query in cache:
        del cache[query]
        _save_cache(cache)
