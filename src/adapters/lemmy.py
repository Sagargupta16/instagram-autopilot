"""Lemmy federated API v3 (no auth) with primary -> fallback instance."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

_INSTANCES = ("lemmy.world", "lemmy.ml", "sh.itjust.works")
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _try_instance(instance: str, community: str, limit: int) -> list[str] | None:
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
    return [p["post"]["name"] for p in posts if p.get("post", {}).get("name")]


def fetch_hot_posts(community: str, limit: int = 10) -> list[str]:
    """Return hot post titles from `community`, trying instances in order."""
    for instance in _INSTANCES:
        titles = _try_instance(instance, community, limit)
        if titles is not None:
            return titles
    return []
