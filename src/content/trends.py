"""Fetch trending AI/creativity topics from HN + Reddit in parallel.

Grounds daily post ideas in current conversations instead of Claude's
training data alone. Degrades gracefully -- if a source fails, the rest
still work.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.adapters import hackernews, reddit

log = logging.getLogger(__name__)


def fetch_trending_topics(limit: int = 15) -> list[str]:
    """Return up to `limit` trending AI/creativity headlines, deduplicated."""
    tasks: list[tuple[str, tuple]] = [
        ("hn-ai", (hackernews.search_stories, "artificial intelligence", 4)),
        ("hn-gen", (hackernews.search_stories, "generative AI", 3)),
        ("hn-prompt", (hackernews.search_stories, "prompt engineering", 2)),
        ("reddit-singularity", (reddit.fetch_top, "singularity", 4)),
        ("reddit-stablediffusion", (reddit.fetch_top, "StableDiffusion", 3)),
        ("reddit-openai", (reddit.fetch_top, "OpenAI", 3)),
        ("reddit-artificial", (reddit.fetch_top, "artificial", 3)),
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
