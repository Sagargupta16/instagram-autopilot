"""Generate images via Bedrock Nova Canvas."""

from __future__ import annotations

import base64
import logging

from src.adapters.bedrock import invoke_model

log = logging.getLogger(__name__)

DEFAULT_NEGATIVE_PROMPT = (
    # text and UI
    "text, watermark, logo, words, letters, numbers, signature, caption, subtitle, UI, "
    # quality issues
    "blurry, out of focus, low resolution, pixelated, jpeg artifacts, compression artifacts, "
    "distorted, deformed, ugly, disfigured, bad anatomy, extra fingers, missing fingers, "
    # stylized / non-photoreal
    "illustration, drawing, painting, cartoon, anime, 3D render, CGI, digital art, "
    "vector art, clipart, sketch, concept art, stylized, cel-shaded, "
    # AI-generated tells
    "airbrushed, plastic skin, waxy skin, perfect skin, smooth skin, uncanny valley, "
    "perfect symmetry, overly sharp, overly saturated, HDR look, oversaturated, "
    "fake-looking, synthetic, surreal, dreamlike, glowing unnaturally, "
    # generic / boring
    "stock photo, generic, boring composition, flat lighting, studio perfect"
)


def generate_image(
    prompt: str,
    model_id: str,
    *,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 6.5,
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
