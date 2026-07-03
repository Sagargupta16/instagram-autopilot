"""Entry point: plan today's pillar(s), publish immediately.

Timing is owned by the GitHub Actions cron schedule -- when this process
runs, it publishes now. plan_today still decides HOW MANY posts today
(0-N) and WHICH pillars, but the historical slot times are only used as
idempotency keys, not as sleep targets.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import UTC, datetime
from typing import Any

from src.adapters import bedrock, cloudinary_host, composio
from src.content.caption import generate_caption
from src.content.dedup import record_post, record_slot, slot_already_posted
from src.content.topic import generate_topic
from src.flows.carousel_flow import post_carousel
from src.flows.image_flow import post_image
from src.flows.reel_flow import post_reel
from src.pillar import load_config
from src.schedule import SlotPlan, plan_today
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _preflight_all_auth(text_model_id: str) -> None:
    bedrock.verify_auth(text_model_id)
    composio.verify_auth()
    cloudinary_host.verify_auth()


def _run_slot(slot: SlotPlan, config: dict[str, Any], *, dry_run: bool) -> None:
    pillar = slot.pillar
    log.info("Publishing slot %s | pillar %s", slot.time_utc, pillar["id"])
    content_type = random.choice(settings.content_type_list)
    topic = generate_topic(pillar, content_type)
    caption_data = generate_caption(topic, pillar, config["persona"])
    caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    log.info("X post: %s", caption_data["x_post"])
    if not dry_run:
        record_post(topic, caption_data.get("image_prompts", []))
    if dry_run:
        log.info("DRY RUN | topic: %s | caption: %s...", topic, caption[:200])
    image_model = config["models"]["image"]
    video_model = config["models"]["video"]
    content_format = pillar.get("content_format", "carousel")
    if content_format == "reel":
        post_reel(caption_data, caption, image_model, video_model, dry_run=dry_run)
    elif content_format == "image":
        post_image(caption_data, caption, image_model, dry_run=dry_run)
    else:
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)


def run(*, dry_run: bool = False) -> None:
    cloudinary_host.configure()
    config = load_config()

    plan = plan_today(datetime.now(UTC).date(), config.get("cadence", {}), config["pillars"])
    if not plan:
        log.info("No slots planned today. Skipping.")
        return
    log.info(
        "Today's plan: %s",
        [(s.time_utc, s.pillar["id"], s.skip) for s in plan],
    )

    _preflight_all_auth(config["models"]["text"])

    today_iso = datetime.now(UTC).date().isoformat()
    for slot in plan:
        if slot.skip:
            log.info("Skip flag set on slot %s -- skipping", slot.time_utc)
            continue
        # Same-day idempotency: workflow_dispatch replays the identical
        # seeded plan; skip slots that already published today so we do
        # not double-post.
        if not dry_run and slot_already_posted(today_iso, slot.time_utc, slot.pillar["id"]):
            log.info(
                "Slot %s / %s already posted today -- skipping",
                slot.time_utc,
                slot.pillar["id"],
            )
            continue
        try:
            _run_slot(slot, config, dry_run=dry_run)
        except Exception as e:
            log.exception("Slot %s failed: %s", slot.time_utc, e)
            continue
        if not dry_run:
            record_slot(today_iso, slot.time_utc, slot.pillar["id"])

    log.info("Done!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Autopilot")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't publish")
    args = parser.parse_args()

    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Types: %s", settings.niche, settings.content_type_list)
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
