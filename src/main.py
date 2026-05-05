"""Entry point: route today's pillar to the appropriate publishing flow."""

from __future__ import annotations

import argparse
import logging
import random
import sys

from src.adapters import bedrock, cloudinary_host, composio
from src.content.caption import generate_caption
from src.content.dedup import record_post
from src.content.topic import generate_topic
from src.flows.carousel_flow import post_carousel
from src.flows.image_flow import post_image
from src.flows.reel_flow import post_reel
from src.pillar import get_todays_pillar, load_config
from src.schedule import apply_jitter
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _preflight_all_auth(text_model_id: str) -> None:
    """Verify Bedrock, Composio, and Cloudinary creds BEFORE the jitter sleep.

    Any of these failing after a 0-180 min sleep would waste hours of runtime.
    Cloudinary and Bedrock raise on bad creds; Composio's preflight logs+raises.
    """
    bedrock.verify_auth(text_model_id)
    composio.verify_auth()
    cloudinary_host.verify_auth()


def run(*, dry_run: bool = False) -> None:
    """Generate and publish one piece of content to Instagram."""
    cloudinary_host.configure()
    config = load_config()

    pillar = get_todays_pillar(config)
    if pillar is None:
        log.info("No pillar scheduled for today. Skipping.")
        return

    # Fail fast on expired creds BEFORE sleeping 0-180 min for jitter --
    # otherwise a bad token wastes hours of runtime.
    _preflight_all_auth(config["models"]["text"])

    # Randomize actual post time inside the engagement window so the
    # account does not look bot-scheduled. Skipped on dry-run.
    if not dry_run:
        apply_jitter(settings.post_jitter_max_minutes)

    log.info("Pillar: %s", pillar["label"])
    content_type = random.choice(settings.content_type_list)
    log.info("Content type: %s", content_type)

    topic = generate_topic(pillar, content_type)
    caption_data = generate_caption(topic, pillar, config["persona"])

    caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    log.info("X post: %s", caption_data["x_post"])

    # Record BEFORE publishing so a publish failure does not let us retry
    # the same topic/scenes tomorrow. Skipped on dry-run so we do not
    # pollute history with experiments.
    if not dry_run:
        record_post(topic, caption_data.get("image_prompts", []))

    if dry_run:
        log.info("=== DRY RUN ===")
        log.info("Topic: %s", topic)
        log.info("Caption: %s...", caption[:200])

    image_model = config["models"]["image"]
    video_model = config["models"]["video"]
    content_format = pillar.get("content_format", "carousel")

    if content_format == "reel":
        post_reel(caption_data, caption, image_model, video_model, dry_run=dry_run)
    elif content_format == "image":
        post_image(caption_data, caption, image_model, dry_run=dry_run)
    else:
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)

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
