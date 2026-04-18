"""Generate images using AWS Bedrock Nova Canvas."""

from __future__ import annotations

import base64
import logging

import requests

from src.config import settings

log = logging.getLogger(__name__)

BEDROCK_INVOKE_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"


DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, logo, words, letters, numbers, signature, caption, subtitle, "
    "blurry, out of focus, low resolution, pixelated, grainy, noisy, jpeg artifacts, "
    "compression artifacts, low quality, amateur, poorly lit, flat lighting, "
    "oversaturated, washed out, distorted, deformed, ugly, disfigured, "
    "stock photo, generic, clipart, cartoon unless requested, boring composition"
)


def generate_image(
    prompt: str,
    model_id: str,
    *,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 9.0,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
) -> bytes:
    """Generate an image from a text prompt via Bedrock Nova Canvas.

    Returns raw PNG bytes (no file saved to disk).
    """
    url = BEDROCK_INVOKE_URL.format(
        region=settings.aws_region,
        model=model_id,
    )

    body = {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": prompt,
            "negativeText": negative_prompt,
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "width": width,
            "height": height,
            "quality": "premium",
            "cfgScale": cfg_scale,
        },
    }

    resp = requests.post(
        url,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
        },
        timeout=120,
    )
    if not resp.ok:
        log.error("Bedrock %s returned %s: %s", resp.status_code, resp.reason, resp.text)
        resp.raise_for_status()

    result = resp.json()
    image_b64 = result["images"][0]
    image_bytes = base64.b64decode(image_b64)

    log.info("Generated image (%d bytes) via %s", len(image_bytes), model_id)
    return image_bytes
