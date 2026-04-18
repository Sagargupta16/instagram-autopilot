"""Main entry point: generate content and publish to Instagram + X."""

from __future__ import annotations

import argparse
import logging
import random
import sys

from src.config import get_todays_pillar, load_config, settings
from src.generator.image import generate_image
from src.generator.reel import generate_reel
from src.generator.text import generate_caption, generate_topic
from src.publisher.instagram import publish_image_post, publish_reel
from src.publisher.twitter import publish_text_post
from src.utils.image_host import upload_to_imgbb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _post_image(
    caption_data: dict[str, str],
    config: dict,
    instagram_caption: str,
    *,
    dry_run: bool,
) -> None:
    """Generate an AI image and publish to Instagram + X."""
    image_prompt = caption_data["image_prompt"]
    log.info("Image prompt: %s", image_prompt)

    image_bytes = generate_image(
        prompt=image_prompt,
        model_id=config["models"]["image"],
    )

    if dry_run:
        log.info("DRY RUN: Generated %d bytes of image data", len(image_bytes))
        return

    image_url = upload_to_imgbb(image_bytes, settings.imgbb_api_key)

    publish_image_post(
        image_url=image_url,
        caption=instagram_caption,
        api_key=settings.composio_api_key,
    )

    publish_text_post(text=caption_data["x_post"], api_key=settings.composio_api_key)


def _post_reel(
    caption_data: dict[str, str],
    config: dict,
    instagram_caption: str,
    *,
    dry_run: bool,
) -> None:
    """Generate an AI video and publish as Instagram Reel."""
    video_prompt = caption_data["video_prompt"]
    log.info("Video prompt: %s", video_prompt)

    if not settings.s3_video_bucket:
        log.warning("S3_VIDEO_BUCKET not set -- falling back to image post")
        _post_image(caption_data, config, instagram_caption, dry_run=dry_run)
        return

    video_s3_uri = generate_reel(
        prompt=video_prompt,
        model_id=config["models"]["video"],
        s3_output_uri=settings.s3_video_bucket,
    )

    if dry_run:
        log.info("DRY RUN: Video at %s", video_s3_uri)
        return

    publish_reel(
        video_url=video_s3_uri,
        caption=instagram_caption,
        api_key=settings.composio_api_key,
    )

    publish_text_post(text=caption_data["x_post"], api_key=settings.composio_api_key)


def run(*, dry_run: bool = False) -> None:
    """Generate and publish one piece of content to Instagram and X."""
    config = load_config()

    pillar = get_todays_pillar(config)
    if pillar is None:
        log.info("No pillar scheduled for today (Sunday). Skipping.")
        return

    log.info("Pillar: %s", pillar["label"])

    content_type = random.choice(settings.content_type_list)
    log.info("Content type: %s", content_type)

    # 1. Generate topic
    topic = generate_topic(pillar, content_type)

    # 2. Generate caption, prompts for image/video, and X post
    persona = config["persona"]
    caption_data = generate_caption(topic, pillar, persona)

    instagram_caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    log.info("X post: %s", caption_data["x_post"])

    if dry_run:
        log.info("=== DRY RUN ===")
        log.info("Topic: %s", topic)
        log.info("Caption: %s", instagram_caption[:200] + "...")

    # 3. Generate media and publish based on pillar's content format
    content_format = pillar.get("content_format", "image")

    if content_format == "reel":
        _post_reel(caption_data, config, instagram_caption, dry_run=dry_run)
    else:
        _post_image(caption_data, config, instagram_caption, dry_run=dry_run)

    log.info("Done!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Autopilot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate content but skip publishing (for testing)",
    )
    args = parser.parse_args()

    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Types: %s", settings.niche, settings.content_type_list)

    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
