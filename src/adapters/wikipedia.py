"""Wikipedia pageviews REST API (no auth).

Top-1000 English-Wikipedia articles by pageviews for date - 2 days
(pageviews data lags ~2 days). Cross-category signal of public curiosity.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import requests

from src.content.sources import records_or_titles, source_record

log = logging.getLogger(__name__)

_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}/{m}/{d}"
_EXTRACTS_URL = "https://en.wikipedia.org/w/api.php"
EXTRACT_CHARS = 1600
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
_SKIP_PREFIXES = ("Special:", "Wikipedia:", "Portal:", "Help:")
_SKIP_EXACT = {"Main_Page", "-"}


def fetch_top_articles(
    limit: int = 20, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Return pageview signals; their observation date is not a publication date."""
    if limit <= 0:
        return []
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
    records = [
        source_record(
            a["article"].replace("_", " "),
            "wikipedia",
            "general",
            url=f"https://en.wikipedia.org/wiki/{quote(a['article'], safe='')}",
            observed_at=day.isoformat(),
        )
        for a in articles
        if a.get("article")
        and a["article"] not in _SKIP_EXACT
        and not a["article"].startswith(_SKIP_PREFIXES)
    ]
    return records_or_titles(records[:limit], include_metadata)


def _intro_extracts(titles: list[str]) -> dict[str, str]:
    """Plain-text lead sections for up to 20 titles in one request; empty on failure."""
    try:
        resp = requests.get(
            _EXTRACTS_URL,
            params={
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": 20,
                "redirects": 1,
                "titles": "|".join(titles[:20]),
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Wikipedia extracts fetch failed: %s", e)
        return {}
    if not resp.ok:
        log.warning("Wikipedia extracts HTTP %s", resp.status_code)
        return {}
    query = resp.json().get("query", {})
    renamed = {
        entry.get("from"): entry.get("to")
        for entry in query.get("normalized", []) + query.get("redirects", [])
    }
    pages = {
        page.get("title"): page.get("extract")
        for page in query.get("pages", [])
        if isinstance(page.get("extract"), str) and page["extract"].strip()
    }
    extracts: dict[str, str] = {}
    for requested in titles[:20]:
        title = requested
        for _ in range(4):  # normalized, then redirected, possibly more than once
            title = renamed.get(title, title)
        if title in pages:
            extracts[requested] = pages[title]
    return extracts


def fetch_top_articles_with_extracts(
    limit: int = 12, *, include_metadata: bool = False
) -> list[str] | list[dict[str, str]]:
    """Pageview signals plus each article's lead section as dated, quotable evidence."""
    records = fetch_top_articles(limit, include_metadata=True)
    extracts = _intro_extracts([record["title"] for record in records]) if records else {}
    enriched = [
        source_record(
            record["title"],
            "wikipedia",
            "general",
            excerpt_limit=EXTRACT_CHARS,
            url=record.get("url"),
            observed_at=record.get("observed_at"),
            excerpt=extracts.get(record["title"]),
        )
        for record in records
    ]
    return records_or_titles(enriched, include_metadata)
