"""Wikipedia pageviews REST API (no auth).

Top-1000 English-Wikipedia articles by pageviews for date - 2 days
(pageviews data lags ~2 days). Cross-category signal of public curiosity.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import requests

log = logging.getLogger(__name__)

_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}/{m}/{d}"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
_SKIP_PREFIXES = ("Special:", "Wikipedia:", "Portal:", "Help:")
_SKIP_EXACT = {"Main_Page", "-"}


def fetch_top_articles(limit: int = 20) -> list[str]:
    """Return up to `limit` most-viewed English Wikipedia article titles."""
    day = datetime.now(UTC).date() - timedelta(days=2)
    url = _URL.format(y=day.year, m=f"{day.month:02d}", d=f"{day.day:02d}")
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
    except requests.RequestException as e:
        log.warning("Wikipedia pageviews fetch failed: %s", e)
        return []
    if not resp.ok:
        log.warning("Wikipedia pageviews HTTP %s", resp.status_code)
        return []
    items = resp.json().get("items", [])
    if not items:
        return []
    articles = items[0].get("articles", [])
    titles = [
        a["article"].replace("_", " ")
        for a in articles
        if a.get("article")
        and a["article"] not in _SKIP_EXACT
        and not a["article"].startswith(_SKIP_PREFIXES)
    ]
    return titles[:limit]
