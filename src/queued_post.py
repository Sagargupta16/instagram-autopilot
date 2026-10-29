"""A claimed slot filled from the private Reel queue instead of generated content: the same
claim, checkpoint, receipt and summary rules as a generated post, but no fallback chain. A
queued video either posts or stays in the queue for the next run."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from src import checkpoint
from src.adapters import cloudinary_host, composio
from src.adapters.reel_queue import QueuedReel, ReelQueue
from src.content.dedup import record_post
from src.flows.queued_reel_flow import post_queued_reel
from src.run_report import write_summary
from src.state.ledger import Ledger

log = logging.getLogger(__name__)


def published_titles(slots: dict[str, Any]) -> set[str]:
    """Topics with a published receipt: a queued title among them never posts again."""
    return {
        entry["topic"]
        for entry in slots.values()
        if entry.get("status") == "published" and entry.get("topic")
    }


def post(
    item: QueuedReel,
    queue: ReelQueue,
    key: str,
    config: dict[str, Any],
    ledger: Ledger | None,
    *,
    clock: Callable[[], datetime],
    dry_run: bool,
) -> dict[str, Any]:
    entry = item.entry
    try:
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
    except Exception as error:
        if ledger:
            ledger.fail(key, type(error).__name__, clock())
        write_summary({"status": "failed", "slot": key, "error": type(error).__name__})
        raise RuntimeError(f"Publication failed for {key}; inspect the durable receipt") from error
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
    status = "preview" if dry_run else "published"
    result = {"status": status, "slot": key, "media_id": media_id, "queued": item.slug}
    write_summary(result)
    return result
