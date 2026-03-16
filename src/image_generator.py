"""Generate images using Bedrock Titan Image Generator."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import boto3

from src.config import settings

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _get_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def generate_post_image(
    topic: str,
    style: str = "modern, clean, vibrant colors, instagram aesthetic",
    width: int = 1080,
    height: int = 1350,
) -> Path:
    """Generate a single post image. Returns path to saved image."""
    client = _get_bedrock_client()

    prompt = (
        f"Create a visually striking Instagram post image about: {topic}. "
        f"Style: {style}. "
        "No text in the image. High quality, professional photography style. "
        "Clean composition suitable for social media."
    )

    response = client.invoke_model(
        modelId=settings.bedrock_image_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "textToImageParams": {"text": prompt},
                "taskType": "TEXT_IMAGE",
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "width": width,
                    "height": height,
                    "cfgScale": 8.0,
                },
            }
        ),
    )

    result = json.loads(response["body"].read())
    image_data = base64.b64decode(result["images"][0])

    output_path = OUTPUT_DIR / f"post_{topic[:30].replace(' ', '_')}.png"
    output_path.write_bytes(image_data)
    return output_path


def generate_carousel_images(
    slides: list[dict[str, str]],
    topic: str,
) -> list[Path]:
    """Generate images for each carousel slide. Returns list of image paths."""
    paths: list[Path] = []

    for i, slide in enumerate(slides):
        slide_text = slide.get("text", slide.get("title", topic))
        image_path = generate_post_image(
            topic=f"{topic} - {slide_text}",
            style="minimal, clean background, infographic style, bold typography friendly",
            width=1080,
            height=1080,
        )
        # Rename with slide number
        new_path = OUTPUT_DIR / f"carousel_{i:02d}.png"
        image_path.rename(new_path)
        paths.append(new_path)

    return paths


def generate_reel_background(topic: str) -> Path:
    """Generate a background image for a Reel. Returns path to image."""
    return generate_post_image(
        topic=topic,
        style="cinematic, moody, atmospheric, dark background, subtle",
        width=1080,
        height=1920,
    )
