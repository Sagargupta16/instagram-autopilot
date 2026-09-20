"""Generate Instagram caption, X post, 5 image prompts, and video prompt."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.adapters.bedrock import invoke_claude
from src.content.dedup import load_recent_image_prompts
from src.content.schemas import CaptionContent
from src.content.validation import generate_validated
from src.pillar import load_config
from src.settings import settings

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "caption.txt"

# How many recent image prompts to show Claude so it can avoid repeats.
# Higher = more variety pressure but more tokens spent.
RECENT_SCENE_LIMIT = 15
# Truncate each recent prompt to the "subject + environment" portion (first ~120 chars).
# That's what drives visual similarity; camera/lens/film cues repeat harmlessly.
RECENT_SCENE_SNIPPET_CHARS = 140


def _format_recent_scenes(prompts: list[str]) -> str:
    if not prompts:
        return "(no history yet)"
    return "\n".join(f"- {p[:RECENT_SCENE_SNIPPET_CHARS].strip()}" for p in prompts)


def generate_caption(
    topic: str,
    pillar: dict[str, Any],
    persona: dict[str, Any],
    *,
    sources: list[dict] | None = None,
) -> dict[str, Any]:
    """Return validated publishing fields plus five alt texts and optional slide notes."""
    recent_prompts = load_recent_image_prompts(limit=RECENT_SCENE_LIMIT)
    recent_scenes = _format_recent_scenes(recent_prompts)

    style_hint = pillar.get("image_style") or "editorial documentary photography"

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        niche=settings.niche,
        pillar=pillar["label"],
        topic=topic,
        tone=persona["tone"],
        pillar_hashtags=" ".join(pillar["hashtags"]),
        style_hint=style_hint,
        recent_scenes=recent_scenes,
        sources=json.dumps(sources or [], ensure_ascii=False),
    )

    config = load_config()
    content = generate_validated(
        prompt,
        lambda text: invoke_claude(config["models"]["text"], text, max_tokens=4096),
        CaptionContent.model_validate,
    )
    data = content.model_dump()

    log.info(
        "Generated caption (%d chars), X post (%d chars), %d image prompts; %d recent scenes shown",
        len(data["caption"]),
        len(data["x_post"]),
        len(data.get("image_prompts", [])),
        len(recent_prompts),
    )
    return data
