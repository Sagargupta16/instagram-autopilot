"""Generate images via Bedrock Stable Image Ultra.

Key Stable Image Ultra levers we rely on (ref: AWS Bedrock Stability docs):
    - Request shape is `prompt` + `negative_prompt` + `aspect_ratio` --
      no width/height, no cfgScale, no style enum. Photorealism comes from
      the photographic vocabulary in the prompt itself (camera, lens, film
      stock cues), which prompts/caption.txt already enforces.
    - `seed`  0 means random ON THE SERVICE SIDE, but we still pick a fresh
      random seed per call so the value is logged and reproducible.
    - Content moderation surfaces in `finish_reasons` -- a non-null entry
      means the image was filtered. We raise a clear error instead of
      returning a black frame.
"""

from __future__ import annotations

import base64
import logging
import random

from src.adapters.bedrock import invoke_model

log = logging.getLogger(__name__)

# Stability caps prompt and negative_prompt at 10k chars; we keep our own
# lower cap so runaway template edits get flagged in logs instead of
# silently producing bloated prompts that dilute the subject.
MAX_PROMPT_CHARS = 2000

# Stable Image Ultra seed range per Stability docs (0 = random server-side).
SEED_MIN = 1
SEED_MAX = 4_294_967_294

# Stability has no native photorealism enum, so the negative prompt carries
# both photo-specific failure modes AND the anti-illustration guard:
DEFAULT_NEGATIVE_PROMPT = (
    # style guard (no native PHOTOREALISM enum like Nova Canvas had)
    "illustration, cartoon, anime, 3D render, CGI, painting, drawing, sketch, "
    # text artifacts
    "text, watermark, logo, words, letters, numbers, signature, caption, subtitle, UI, "
    # quality issues
    "blurry, out of focus, low resolution, pixelated, jpeg artifacts, "
    "distorted, deformed, bad anatomy, extra fingers, missing fingers, "
    # AI-generated tells in photoreal mode
    "plastic skin, waxy skin, perfect skin, smooth skin, uncanny valley, "
    "perfect symmetry, oversaturated, HDR look, airbrushed, fake-looking, "
    # generic composition
    "stock photo, flat lighting, studio perfect, boring composition"
)


def _truncate_prompt(prompt: str, limit: int) -> str:
    if len(prompt) <= limit:
        return prompt
    log.warning(
        "Image prompt too long (%d chars > %d cap) -- truncating to keep the subject dominant",
        len(prompt),
        limit,
    )
    return prompt[:limit]


def generate_image(
    prompt: str,
    model_id: str,
    *,
    aspect_ratio: str = "1:1",
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    seed: int | None = None,
) -> bytes:
    """Generate an image from a text prompt. Returns raw PNG bytes.

    `seed=None` (default) picks a fresh random seed per call so images do not
    collapse toward the same composition across days. Pass an explicit int for
    reproducible generation (useful when iterating on a prompt).
    """
    safe_prompt = _truncate_prompt(prompt, MAX_PROMPT_CHARS)
    safe_negative = _truncate_prompt(negative_prompt, MAX_PROMPT_CHARS)
    chosen_seed = seed if seed is not None else random.randint(SEED_MIN, SEED_MAX)

    body = {
        "prompt": safe_prompt,
        "negative_prompt": safe_negative,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "seed": chosen_seed,
    }
    result = invoke_model(model_id, body)

    finish_reasons = result.get("finish_reasons") or []
    if finish_reasons and finish_reasons[0]:
        raise RuntimeError(f"Stability filtered the image: {finish_reasons[0]}")

    images = result.get("images") or []
    if not images:
        err = result.get("errors") or result.get("error") or "no images returned"
        raise RuntimeError(f"Stable Image Ultra returned no images: {err}")

    image_bytes = base64.b64decode(images[0])
    log.info(
        "Generated image (%d bytes, seed=%d, ar=%s) via %s",
        len(image_bytes),
        chosen_seed,
        aspect_ratio,
        model_id,
    )
    return image_bytes
