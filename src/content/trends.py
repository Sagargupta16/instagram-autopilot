"""Fetch trending AI/creativity topics from 5 sources in parallel.

Grounds daily post ideas in current conversations instead of Claude's
training data alone. Degrades gracefully -- if a source fails, the rest
still work.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.adapters import github_trending, hackernews, huggingface_papers, producthunt, reddit

log = logging.getLogger(__name__)


def fetch_trending_topics(limit: int = 20) -> list[str]:
    """Return up to `limit` trending AI/creativity headlines, deduplicated."""
    tasks: list[tuple[str, tuple]] = [
        ("hf-daily", (huggingface_papers.fetch_daily_papers, 8)),
        ("ph-ai", (producthunt.fetch_ai_launches, 6)),
        ("gh-genai", (github_trending.fetch_trending, "generative-ai", 5)),
        ("gh-llm", (github_trending.fetch_trending, "llm", 4)),
        ("hn-ai", (hackernews.search_stories, "artificial intelligence", 4)),
        ("hn-gen", (hackernews.search_stories, "generative AI", 3)),
        ("hn-prompt", (hackernews.search_stories, "prompt engineering", 2)),
        ("reddit-localllama", (reddit.fetch_top, "LocalLLaMA", 3)),
        ("reddit-stablediffusion", (reddit.fetch_top, "StableDiffusion", 3)),
        ("reddit-singularity", (reddit.fetch_top, "singularity", 3)),
        ("reddit-midjourney", (reddit.fetch_top, "midjourney", 3)),
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
