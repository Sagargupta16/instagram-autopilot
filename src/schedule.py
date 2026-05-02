"""Posting schedule: randomize fire time within an engagement window.

Heuristic now, engagement-driven later. For a brand-new account with no
follower data, we use a published-research "good window" (Later/Sprout
Social 2024-2025: Instagram engagement peaks 10 AM - 4 PM local).

A GitHub Actions cron fires at the START of the window; this module
sleeps a random 0..max_minutes before running, so the actual post time
varies day-to-day instead of being a predictable fixed-minute cron.

Once the account has ~30 posts of reach/like data, swap `apply_jitter`
for a schedule that samples from the empirical best-performing hours
(pulled via Composio Instagram insights). Not built yet -- see
TODO below.
"""

from __future__ import annotations

import logging
import random
import time

log = logging.getLogger(__name__)


def apply_jitter(max_minutes: int) -> None:
    """Sleep a random 0..max_minutes before returning."""
    if max_minutes <= 0:
        return
    sleep_sec = random.randint(0, max_minutes * 60)
    log.info(
        "Jitter: sleeping %d min %d sec before posting",
        sleep_sec // 60,
        sleep_sec % 60,
    )
    time.sleep(sleep_sec)


# TODO: once the account has >=30 posts with insights data, add
# `sample_best_hour()` that pulls engagement histograms from Composio
# Instagram and samples the next post time from the top-quartile hours.
