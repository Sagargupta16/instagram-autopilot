"""Fetch trending AI/creativity topics from free public APIs.

Used to ground daily post ideas in current conversations instead of
generating from Claude's training data alone.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

log = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
REDDIT_TOP_URL = "https://www.reddit.com/r/{subreddit}/top.json"

_AI_KEYWORDS = (
    "AI",
    "artificial intelligence",
    "LLM",
    "GPT",
    "Claude",
    "Gemini",
    "Stable Diffusion",
    "Midjourney",
    "Nano Banana",
    "Veo",
    "Sora",
    "prompt engineering",
    "diffusion",
    "generative",
    "creative AI",
)

_REDDIT_HEADERS = {"User-Agent": "instagram-autopilot/0.5 (trends-fetcher)"}


def _fetch_hackernews(query: str, limit: int = 5) -> list[str]:
    """Fetch top HN stories matching a query from the last week."""
    resp = requests.get(
        HN_SEARCH_URL,
        params={
            "query": query,
            "tags": "story",
            "numericFilters": "points>50",
            "hitsPerPage": limit,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return [hit["title"] for hit in resp.json().get("hits", []) if hit.get("title")]


def _fetch_reddit(subreddit: str, limit: int = 5) -> list[str]:
    """Fetch top posts from a subreddit (no auth, public JSON endpoint)."""
    resp = requests.get(
        REDDIT_TOP_URL.format(subreddit=subreddit),
        params={"t": "week", "limit": limit},
        headers=_REDDIT_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    children = resp.json().get("data", {}).get("children", [])
    return [c["data"]["title"] for c in children if c.get("data", {}).get("title")]


def fetch_trending_topics(limit: int = 15) -> list[str]:
    """Fetch a mix of trending AI/creativity topics from HN and Reddit.

    Returns up to `limit` short headlines. Silently degrades to empty list
    on any network failure -- trends are nice-to-have, not required.
    """
    tasks: list[tuple[str, tuple]] = [
        ("hn-ai", (_fetch_hackernews, "artificial intelligence", 4)),
        ("hn-gen", (_fetch_hackernews, "generative AI", 3)),
        ("hn-prompt", (_fetch_hackernews, "prompt engineering", 2)),
        ("reddit-singularity", (_fetch_reddit, "singularity", 4)),
        ("reddit-stablediffusion", (_fetch_reddit, "StableDiffusion", 3)),
        ("reddit-openai", (_fetch_reddit, "OpenAI", 3)),
        ("reddit-artificial", (_fetch_reddit, "artificial", 3)),
    ]

    results: list[str] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(fn, *args): name for name, (fn, *args) in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as e:
                log.warning("Trend source %s failed: %s", name, e)

    seen: set[str] = set()
    deduped = [t for t in results if not (t in seen or seen.add(t))]

    log.info("Fetched %d trending topics from %d sources", len(deduped), len(tasks))
    return deduped[:limit]
