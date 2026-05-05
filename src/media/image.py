"""Generate images via Bedrock Nova Canvas.

Key Nova Canvas levers we rely on (ref: AWS Nova docs, image-gen-req-resp-structure):
    - `style: "PHOTOREALISM"`  native enum -- does the heavy lifting of keeping
      output photoreal. This replaces a large chunk of what the negative prompt
      used to enforce manually (no illustration / no 3D render / no cartoon).
    - `seed`  default is 12 (NOT random). Unless explicitly randomized, every
      call starts from the same initial noise and tends toward similar
      compositions across days. We pick a fresh random seed per call.
    - `cfgScale: 7.5`  Nova Canvas docs describe 4-7 as "balanced" and 8-10 as
      "strict prompt adherence". 7.5 sits at the strict edge without the
      oversaturated feel of 9-10. Critical for carousels where Claude's 5
      prompts are deliberately different -- stricter adherence means the
      renderer actually honors those differences.
    - RAI moderation may drop images silently; `result["images"]` can be
      shorter than `numberOfImages`. We raise a clear error instead of
      IndexError when the list comes back empty.
"""

from __future__ import annotations

import base64
import logging
import random

from src.adapters.bedrock import invoke_model

log = logging.getLogger(__name__)

# Nova Canvas hard-caps text and negativeText at 1024 chars each. Leave a small
# safety margin so formatting tweaks in the template never push us over.
MAX_PROMPT_CHARS = 1000

# Nova Canvas seed range per AWS docs.
SEED_MIN = 0
SEED_MAX = 2_147_483_646

# With `style: "PHOTOREALISM"` handling "no illustration / no cartoon / no 3D"
# natively, the negative prompt only needs to list photo-specific failure modes:
# text artifacts (Nova Canvas hallucinates gibberish letters otherwise), AI
# tells (plastic skin, uncanny symmetry, HDR look), and anatomical issues.
# Shorter = less chance of crowding out legitimate prompt content.
DEFAULT_NEGATIVE_PROMPT = (
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
        "Image prompt too long (%d chars > %d cap) -- truncating to stay within Nova Canvas limits",
        len(prompt),
        limit,
    )
    return prompt[:limit]


def generate_image(
    prompt: str,
    model_id: str,
    *,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 7.5,
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
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": safe_prompt,
            "negativeText": safe_negative,
            "style": "PHOTOREALISM",
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "width": width,
            "height": height,
            "quality": "premium",
            "cfgScale": cfg_scale,
            "seed": chosen_seed,
        },
    }
    result = invoke_model(model_id, body)
    images = result.get("images") or []
    if not images:
        # RAI content filter may strip all images; `error` is populated then.
        err = result.get("error") or "no images returned (possibly RAI-filtered)"
        raise RuntimeError(f"Nova Canvas returned no images: {err}")
    image_bytes = base64.b64decode(images[0])
    log.info(
        "Generated image (%d bytes, seed=%d, cfg=%.1f) via %s",
        len(image_bytes),
        chosen_seed,
        cfg_scale,
        model_id,
    )
    return image_bytes
