"""Entry point: route today's pillar to the appropriate publishing flow."""

from __future__ import annotations

import argparse
import logging
import random
import sys

from src.adapters.cloudinary_host import configure as configure_cloudinary
from src.content.caption import generate_caption
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


def run(*, dry_run: bool = False) -> None:
    """Generate and publish one piece of content to Instagram."""
    configure_cloudinary()
    config = load_config()

    pillar = get_todays_pillar(config)
    if pillar is None:
        log.info("No pillar scheduled for today. Skipping.")
        return

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
