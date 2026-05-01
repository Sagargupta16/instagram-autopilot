"""Generate Instagram caption, X post, 5 image prompts, and video prompt."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.adapters.bedrock import extract_json, invoke_claude
from src.pillar import load_config
from src.settings import settings

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "caption.txt"


def generate_caption(
    topic: str,
    pillar: dict[str, Any],
    persona: dict[str, Any],
) -> dict[str, Any]:
    """Return dict with caption, hashtags, x_post, image_prompts (list of 5), video_prompt."""
    prompt = PROMPT_PATH.read_text().format(
        niche=settings.niche,
        pillar=pillar["label"],
        topic=topic,
        tone=persona["tone"],
        pillar_hashtags=" ".join(pillar["hashtags"]),
    )

    config = load_config()
    raw = invoke_claude(config["models"]["text"], prompt)
    data = extract_json(raw)

    log.info(
        "Generated caption (%d chars), X post (%d chars), %d image prompts",
        len(data["caption"]),
        len(data["x_post"]),
        len(data.get("image_prompts", [])),
    )
    return data
