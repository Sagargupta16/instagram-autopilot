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
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from src.settings import settings

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "cache" / "places.json"
CACHE_TTL_DAYS = 30
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        log.warning("places cache corrupt, resetting")
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    # NOSONAR python:S6931 -- CACHE_PATH is a module-level constant derived
    # from __file__, not user input. Not a path-injection surface.
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=CACHE_PATH.parent, suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(cache, stream, indent=2)
        Path(temporary).replace(CACHE_PATH)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _is_fresh(entry: dict) -> bool:
    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
    except (KeyError, TypeError, ValueError):
        return False
    if cached_at.tzinfo is None:
        return False
    return timedelta(0) <= datetime.now(UTC) - cached_at < timedelta(days=CACHE_TTL_DAYS)


def _located_pages(response: requests.Response) -> list[str]:
    try:
        payload = response.json()
    except ValueError:
        return []
    pages = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(pages, list):
        return []
    ids = []
    for page in pages:
        if not isinstance(page, dict) or not str(page.get("id", "")).isdigit():
            continue
        location = page.get("location")
        if not isinstance(location, dict):
            continue
        latitude, longitude = location.get("latitude"), location.get("longitude")
        if (
            isinstance(latitude, (int, float))
            and not isinstance(latitude, bool)
            and isinstance(longitude, (int, float))
            and not isinstance(longitude, bool)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            ids.append(str(page["id"]))
    return ids


def resolve_location_id(query: str) -> str | None:
    """Return a Facebook Page ID with location data matching `query`, or None."""
    if not query or not settings.meta_user_access_token:
        return None
    cache = _load_cache()
    if query in cache and _is_fresh(cache[query]) and cache[query].get("page_id"):
        return cache[query]["page_id"]
    version = settings.meta_graph_api_version
    url = f"https://graph.facebook.com/{version}/pages/search"
    try:
        resp = requests.get(
            url,
            params={
                "q": query,
                "fields": "id,name,location",
            },
            headers={
                "User-Agent": _UA,
                "Authorization": f"Bearer {settings.meta_user_access_token}",
            },
            timeout=15,
        )
    except requests.RequestException:
        log.warning("Places search network error")
        return None
    if not resp.ok:
        log.warning("Places search HTTP %s", resp.status_code)
        return None
    for page_id in _located_pages(resp):
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


def invalidate_location_id(location_id: str) -> None:
    """Invalidate aliases of a confirmed invalid location, never a media fetch error."""
    cache = _load_cache()
    remaining = {
        query: entry
        for query, entry in cache.items()
        if isinstance(entry, dict) and str(entry.get("page_id")) != location_id
    }
    if remaining != cache:
        _save_cache(remaining)
