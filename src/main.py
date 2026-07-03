"""Entry point: plan today's slots, sleep to each, publish."""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
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
from src.schedule import SlotPlan, plan_today, to_minutes
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


def _sleep_until_utc(target_hhmm: str) -> None:
    now = datetime.now(UTC)
    target_min = to_minutes(target_hhmm)
    now_min = now.hour * 60 + now.minute
    delta = target_min - now_min
    if delta <= 0:
        log.info("Slot %s already past, publishing immediately", target_hhmm)
        return
    log.info("Sleeping %d min until %s UTC", delta, target_hhmm)
    time.sleep(delta * 60)


def _run_slot(slot: SlotPlan, config: dict[str, Any], *, dry_run: bool) -> None:
    pillar = slot.pillar
    log.info("Slot %s | pillar %s", slot.time_utc, pillar["id"])
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


def run(*, dry_run: bool = False, now: bool = False) -> None:
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
        # Same-day idempotency: manual workflow_dispatch on the same date
        # replays the identical plan (same YYYYMMDD seed). Skip slots that
        # already published so we do not double-post.
        if not dry_run and slot_already_posted(today_iso, slot.time_utc, slot.pillar["id"]):
            log.info(
                "Slot %s / %s already posted today -- skipping",
                slot.time_utc,
                slot.pillar["id"],
            )
            continue
        if not dry_run and not now:
            _sleep_until_utc(slot.time_utc)
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
    parser.add_argument(
        "--now",
        action="store_true",
        help="Skip the sleep-until-slot -- publish all planned slots back-to-back. Use for manual test/verify runs.",
    )
    args = parser.parse_args()

    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Types: %s", settings.niche, settings.content_type_list)
    # Manual workflow_dispatch runs should publish immediately, not sleep
    # until the RNG-picked slot time (which can be 8+ hours away and blow
    # past the 480-min runner cap). GITHUB_EVENT_NAME is set by GH Actions.
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    run(dry_run=args.dry_run, now=args.now or is_manual)


if __name__ == "__main__":
    main()
