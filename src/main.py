"""Main entry point: generate content and publish to Instagram + X."""

from __future__ import annotations

import logging
import random
import sys

from src.config import get_todays_pillar, load_config, settings
from src.generator.text import generate_caption, generate_topic
from src.publisher.instagram import publish_image_post
from src.publisher.twitter import publish_text_post
from src.utils.image_host import upload_to_imgbb
from src.utils.template_image import generate_template_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def run() -> None:
    """Generate and publish one piece of content to Instagram and X."""
    config = load_config()

    # Determine today's content pillar
    pillar = get_todays_pillar(config)
    if pillar is None:
        log.info("No pillar scheduled for today (Sunday). Skipping.")
        return

    log.info("Pillar: %s", pillar["label"])

    # Pick a random content type
    content_type = random.choice(settings.content_type_list)
    log.info("Content type: %s", content_type)

    # 1. Generate topic
    topic = generate_topic(pillar, content_type)

    # 2. Generate caption, X post, and image text
    persona = config["persona"]
    caption_data = generate_caption(topic, pillar, persona)

    instagram_caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    x_post = caption_data["x_post"]
    image_text = caption_data["image_text"]

    # 3. Generate template image
    image_path = generate_template_image(
        image_text=image_text,
        pillar_id=pillar["id"],
        image_styles=config["image_styles"],
    )

    # 4. Upload image to imgbb for public URL
    image_url = upload_to_imgbb(image_path, settings.imgbb_api_key)

    # 5. Publish to Instagram
    publish_image_post(
        image_url=image_url,
        caption=instagram_caption,
        api_key=settings.composio_api_key,
    )

    # 6. Publish to X/Twitter (gracefully skips if not connected)
    publish_text_post(text=x_post, api_key=settings.composio_api_key)

    log.info("Done!")


if __name__ == "__main__":
    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Content types: %s", settings.niche, settings.content_type_list)
    run()
