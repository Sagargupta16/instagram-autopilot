"""Lemmy federated API v3 (no auth) with primary -> fallback instance."""

from __future__ import annotations

import logging

import requests

from src.content.sources import records_or_titles, source_record

log = logging.getLogger(__name__)

_INSTANCES = ("lemmy.world", "lemmy.ml", "sh.itjust.works")
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _try_instance(instance: str, community: str, limit: int) -> list[dict[str, str]] | None:
    url = f"https://{instance}/api/v3/post/list"
    try:
        resp = requests.get(
            url,
            params={
                "sort": "Hot",
                "limit": limit,
                "community_name": f"{community}@{instance}",
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Lemmy %s fetch failed: %s", instance, e)
        return None
    if not resp.ok:
        log.warning("Lemmy %s HTTP %s", instance, resp.status_code)
        return None
    posts = resp.json().get("posts", [])
    return [
        source_record(
            entry["post"]["name"],
            "lemmy",
            community,
            url=entry["post"].get("url") or entry["post"].get("ap_id"),
            published_at=entry["post"].get("published"),
            excerpt=entry["post"].get("body"),
        )
        for entry in posts
        if entry.get("post", {}).get("name")
    ][:limit]


def fetch_hot_posts(
    community: str, limit: int = 10, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return community posts, optionally retaining their unverified source text."""
    if limit <= 0:
        return []
    for instance in _INSTANCES:
        records = _try_instance(instance, community, limit)
        if records is not None:
            return records_or_titles(records, include_metadata)
    return []
