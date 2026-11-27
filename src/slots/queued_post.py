"""One queued pair posted into a claimed slot instead of generated content: the same claim,
checkpoint and receipt rules as a generated post, and never a fallback to generated content.
Every pair a run tries goes through `attempt` on its own (`queue_attempts` moves on past a
pair that is bad in its own files)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from src.adapters import cloudinary_host, composio
from src.adapters.reel_queue import QueuedReel, ReelQueue
from src.content.dedup import record_post
from src.flows.queued_reel_flow import post_queued_reel
from src.slots import checkpoint
from src.state.ledger import Ledger

log = logging.getLogger(__name__)


def published_titles(slots: dict[str, Any]) -> set[str]:
    """Topics with a published receipt: a queued title among them never posts again."""
    return {
        entry["topic"]
        for entry in slots.values()
        if entry.get("status") == "published" and entry.get("topic")
    }


def attempt(
    item: QueuedReel,
    queue: ReelQueue,
    key: str,
    config: dict[str, Any],
    ledger: Ledger | None,
    *,
    clock: Callable[[], datetime],
    dry_run: bool,
) -> str | None:
    """Post `item` into the claimed `key` and rename it `posted-`; returns the media ID (None
    for a preview) and raises whatever failed, leaving the receipt to the caller."""
    entry = item.entry
    if not dry_run:
        cloudinary_host.configure()
        composio.verify_auth()
        cloudinary_host.verify_auth()
    if ledger:
        content = {
            "caption": entry.caption,
            "hashtags": entry.hashtags,
            "sources": entry.sources,
            "alt_texts": [entry.alt_text],
        }
        ledger.remember(key, entry.title, content, clock())
        record_post(entry.title)
    guard = None if dry_run else checkpoint.guard(config, ledger, key, clock)
    media_id = post_queued_reel(item, queue, dry_run=dry_run, before_publish=guard)
    if ledger:
        ledger.complete(key, media_id, clock())
    if media_id:
        try:
            queue.mark_posted(item)
        except Exception as error:
            # The published receipt already keeps this title from posting again.
            log.warning(
                "Reel %s published, but queue entry %s was not renamed (%s)",
                media_id,
                item.slug,
                type(error).__name__,
            )
    return media_id
