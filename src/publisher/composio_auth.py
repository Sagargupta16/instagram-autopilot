"""Resolve Composio connected account IDs for the REST API."""

from __future__ import annotations

import logging
from functools import lru_cache

import requests

log = logging.getLogger(__name__)

COMPOSIO_API_BASE = "https://backend.composio.dev/api"


@lru_cache(maxsize=1)
def _fetch_connected_accounts(api_key: str) -> list[dict]:
    """Fetch all active connected accounts from Composio."""
    paths = ("v1/connectedAccounts",)
    header_variants = (
        {"x-api-key": api_key},
        {"Authorization": f"Bearer {api_key}"},
        {"x-api-key": api_key, "Authorization": f"Bearer {api_key}"},
    )
    for path in paths:
        for headers in header_variants:
            resp = requests.get(
                f"{COMPOSIO_API_BASE}/{path}",
                params={"showActiveOnly": "true"},
                headers=headers,
                timeout=30,
            )
            auth_type = "x-api-key" if "x-api-key" in headers else "Bearer"
            if "x-api-key" in headers and "Authorization" in headers:
                auth_type = "both"
            log.info("GET %s [%s] -> %s", path, auth_type, resp.status_code)
            if resp.ok:
                data = resp.json()
                items = data.get("items", data if isinstance(data, list) else [])
                log.info("Fetched %d connected accounts", len(items))
                if items:
                    log.info("First account sample: %s", dict(list(items[0].items())[:5]))
                return items

    log.warning("Failed to fetch connected accounts from Composio")
    return []


def resolve_connected_account_id(
    api_key: str,
    app_name: str,
    hint: str = "",
) -> str | None:
    """Resolve a connected account ID for the given app.

    If *hint* looks like it's already a valid Composio ID (UUID or nanoid),
    returns it as-is. Otherwise queries the connected accounts API and matches
    by app name and optional hint.
    """
    if hint and _looks_like_composio_id(hint):
        return hint

    accounts = _fetch_connected_accounts(api_key)
    if not accounts:
        log.info("No connected accounts found, will omit connectedAccountId")
        return None

    matches = [a for a in accounts if a.get("appName", "").lower() == app_name.lower()]
    if not matches:
        log.warning("No connected %s account found in Composio", app_name)
        return None

    if len(matches) == 1:
        acct_id = matches[0].get("id", "")
        log.info("Resolved %s account: %s", app_name, acct_id)
        return acct_id

    if hint:
        for acct in matches:
            searchable = str(acct)
            if hint in searchable:
                log.info("Resolved %s account by hint '%s': %s", app_name, hint, acct["id"])
                return acct["id"]

    acct_id = matches[0].get("id", "")
    log.info("Multiple %s accounts found, using first: %s", app_name, acct_id)
    return acct_id


def _looks_like_composio_id(value: str) -> bool:
    """Check if a value looks like a Composio account ID (UUID or ca_ nanoid)."""
    if value.startswith("ca_"):
        return True
    parts = value.split("-")
    if len(parts) != 5:
        return False
    expected_lengths = [8, 4, 4, 4, 12]
    return all(
        len(p) == el and all(c in "0123456789abcdef" for c in p.lower())
        for p, el in zip(parts, expected_lengths, strict=True)
    )
