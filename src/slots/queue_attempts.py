"""A run that posts from the private Reel queue (contract 32): the oldest waiting pair, or the
named one, goes into the claimed slot through `queued_post.attempt`.

A pair that cannot post because of its own files, judged on a whole download (`BadPair`), is
set aside: its two assets are renamed `<name>.failed-<stamp>`, never deleted, and the same run
takes the next waiting pair, claiming its slot key again under the window, the cap, the gap and
the attempt budget (`post_attempts.ready`). Only a receipt back at "failed" moves on
(`post_attempts.settled`), so a publish call is never repeated. Any other failure sets nothing
aside and fails the run as before. At most MAX_SET_ASIDE pairs are set aside between published
posts: past that a fault in the checker, the runner or the schema is likelier than another bad
video, so nothing more is renamed. A dry run never renames anything and never moves on.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from src.adapters.reel_queue import BadPair, QueuedReel, QueueError, ReelQueue
from src.slots import post_attempts, queued_post
from src.slots.run_report import Refused, refuse, write_summary
from src.state.ledger import Ledger

log = logging.getLogger(__name__)

MAX_SET_ASIDE = 3


def newest_published(ledger: Ledger) -> datetime | None:
    """The latest `published_at` among the ledger's slots."""
    moments = [
        datetime.fromisoformat(entry["published_at"])
        for entry in ledger.snapshot()["slots"].values()
        if entry.get("published_at")
    ]
    return max(moments, default=None)


class QueueRun:
    def __init__(
        self,
        queue: ReelQueue,
        ledger: Ledger | None,
        clock: Callable[[], datetime],
        *,
        published: set[str],
        dry_run: bool,
        slug: str | None,
    ) -> None:
        self.queue, self.ledger, self.clock = queue, ledger, clock
        self.published, self.dry_run, self.slug = published, dry_run, slug
        self.set_aside: list[dict[str, str]] = []

    def report(self) -> dict[str, Any]:
        """What every summary of this run carries once a pair was set aside."""
        return {"set_aside": list(self.set_aside)} if self.set_aside else {}

    def first(self) -> QueuedReel | None:
        """The pair this run starts with, before any slot is claimed."""
        try:
            return self._take()
        except Refused:
            raise
        except Exception as error:
            if self.set_aside:
                write_summary({"status": "failed", "error": type(error).__name__, **self.report()})
            raise

    def empty(self, post_now: bool) -> dict[str, Any]:
        """With `video_source` "queue" nothing is generated: an empty queue posts nothing."""
        if post_now:
            refuse("the Reel queue is empty", **self.report())
        log.warning("The Reel queue is empty; nothing to post")
        result = {"status": "skipped", "reason": "The Reel queue is empty", **self.report()}
        write_summary(result)
        return result

    def post(self, item: QueuedReel, key: str, config: dict[str, Any]) -> dict[str, Any]:
        """Post into the claimed `key`, moving on past pairs set aside until one posts."""
        while True:
            try:
                media_id = queued_post.attempt(
                    item,
                    self.queue,
                    key,
                    config,
                    self.ledger,
                    clock=self.clock,
                    dry_run=self.dry_run,
                )
                break
            except BadPair as bad:
                if self.dry_run or not post_attempts.settled(self.ledger, key, bad, self.clock()):
                    raise self._failed(key, bad) from bad  # it may have reached Instagram
                item, key = self._move_on(bad, key, config)
            except Exception as error:
                raise self._failed(key, error) from error
        status = "preview" if self.dry_run else "published"
        result = {"status": status, "slot": key, "media_id": media_id, "queued": item.slug}
        result |= self.report()
        write_summary(result)
        return result

    def _take(self) -> QueuedReel | None:
        """The next waiting pair; one whose JSON is bad is set aside and the next is read."""
        while True:
            exclude = frozenset(entry["slug"] for entry in self.set_aside)
            try:
                return self.queue.next_item(
                    published=self.published, slug=self.slug, exclude=exclude
                )
            except BadPair as bad:
                if self.dry_run:
                    raise
                self._set_aside(bad)

    def _set_aside(self, bad: BadPair) -> None:
        """Rename the judged pair under the bound; a named pair then refuses the run. Never
        reached in a dry run, which has no ledger."""
        newest = newest_published(self.ledger) if self.ledger else None
        if self.queue.set_aside_since(newest) >= MAX_SET_ASIDE:
            message = (
                f"{bad}; not set aside: {MAX_SET_ASIDE} pairs were already set aside since the"
                " last post, so look at the checker or the runner"
            )
            log.error("%s", message)
            raise QueueError(message) from bad
        suffix = self.queue.set_aside(bad, self.clock())
        self.set_aside.append({"slug": bad.slug, "reason": bad.reason, "as": suffix})
        log.warning("Set aside queued pair %s as %s: %s", bad.slug, suffix, bad.reason)
        if self.slug is not None:
            refuse(f"queued video {bad.slug} was set aside: {bad.reason}", **self.report())

    def _move_on(self, bad: BadPair, key: str, config: dict[str, Any]) -> tuple[QueuedReel, str]:
        """Set `bad` aside and claim the next pair's slot key (same date and time, its pillar).
        `key` is already settled as failed, so a failure here only ends the run."""
        try:
            self._set_aside(bad)
            item = self._take()
            if item is None:  # the pairs ran out: the slot stays failed under the last key
                raise post_attempts.Failed(key)
            following = f"{key.rsplit('|', 1)[0]}|{item.entry.pillar}"
            if not post_attempts.ready(self.ledger, following, self.clock(), config):
                raise post_attempts.Failed(key)
        except Refused:
            raise
        except Exception as error:
            if isinstance(error, QueueError):  # its words name assets, never an entry's text
                log.error("%s", error)
            raise self._failed(key, error, settled=True) from error
        log.warning("Queued pair %s set aside; trying %s for %s", bad.slug, item.slug, following)
        return item, following

    def _failed(self, key: str, error: Exception, *, settled: bool = False) -> RuntimeError:
        if self.ledger and not settled:
            self.ledger.fail(key, type(error).__name__, self.clock())
        outcome = {"status": "failed", "slot": key, "error": type(error).__name__}
        write_summary({**outcome, **self.report()})
        return RuntimeError(f"Publication failed for {key}; inspect the durable receipt")
