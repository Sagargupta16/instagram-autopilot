"""Main entry point: generate content and publish to Instagram."""

from __future__ import annotations

import logging
import random
import sys

from src.config import settings
from src.content_generator import generate_caption, generate_carousel_slides, generate_reel_script, generate_topic
from src.image_generator import generate_carousel_images, generate_post_image, generate_reel_background
from src.instagram_publisher import InstagramPublisher
from src.media_uploader import upload_image, upload_images, upload_video
from src.tts_generator import generate_voiceover
from src.video_maker import create_reel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def run_single_post() -> None:
    """Generate and publish one piece of content."""
    content_type = random.choice(settings.content_type_list)
    log.info("Content type selected: %s", content_type)

    # 1. Generate topic
    topic_data = generate_topic(content_type)
    topic = topic_data["topic"]
    log.info("Topic: %s", topic)

    # 2. Generate caption
    caption_data = generate_caption(topic, content_type)
    caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    log.info("Caption generated (%d chars)", len(caption))

    publisher = InstagramPublisher()

    if content_type == "reel":
        _publish_reel(topic, caption, publisher)
    elif content_type == "carousel":
        _publish_carousel(topic, caption, publisher)
    else:
        _publish_single_image(topic, caption, publisher)


def _publish_single_image(topic: str, caption: str, publisher: InstagramPublisher) -> None:
    # Generate image
    image_path = generate_post_image(topic)
    log.info("Image generated: %s", image_path)

    # Upload to Cloudinary
    image_url = upload_image(image_path)
    log.info("Uploaded to: %s", image_url)

    # Publish
    media_id = publisher.publish_image(image_url, caption)
    log.info("Published image post: %s", media_id)


def _publish_carousel(topic: str, caption: str, publisher: InstagramPublisher) -> None:
    # Generate slide content
    slides = generate_carousel_slides(topic)
    log.info("Generated %d carousel slides", len(slides))

    # Generate images for each slide
    image_paths = generate_carousel_images(slides, topic)
    log.info("Generated %d carousel images", len(image_paths))

    # Upload all images
    image_urls = upload_images(image_paths)
    log.info("Uploaded %d images to Cloudinary", len(image_urls))

    # Publish carousel
    media_id = publisher.publish_carousel(image_urls, caption)
    log.info("Published carousel: %s", media_id)


def _publish_reel(topic: str, caption: str, publisher: InstagramPublisher) -> None:
    # Generate reel script
    script_data = generate_reel_script(topic)
    voiceover_text = script_data["voiceover"]
    log.info("Reel script generated (%d chars)", len(voiceover_text))

    # Generate background image
    bg_image = generate_reel_background(topic)
    log.info("Background image generated: %s", bg_image)

    # Generate voiceover
    audio_path = generate_voiceover(voiceover_text)
    log.info("Voiceover generated: %s", audio_path)

    # Stitch into video
    video_path = create_reel(bg_image, audio_path, subtitle_text=voiceover_text)
    log.info("Video created: %s", video_path)

    # Upload video
    video_url = upload_video(video_path)
    log.info("Video uploaded: %s", video_url)

    # Publish reel
    media_id = publisher.publish_reel(video_url, caption)
    log.info("Published reel: %s", media_id)


if __name__ == "__main__":
    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Content types: %s", settings.niche, settings.content_type_list)
    run_single_post()
    log.info("Done!")
