"""Generate images via Bedrock Nova Canvas."""

from __future__ import annotations

import base64
import logging

from src.adapters.bedrock import invoke_model

log = logging.getLogger(__name__)

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
    """Generate an image from a text prompt. Returns raw PNG bytes."""
    body = {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt, "negativeText": negative_prompt},
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "width": width,
            "height": height,
            "quality": "premium",
            "cfgScale": cfg_scale,
        },
    }
    result = invoke_model(model_id, body)
    image_bytes = base64.b64decode(result["images"][0])
    log.info("Generated image (%d bytes) via %s", len(image_bytes), model_id)
    return image_bytes
