"""Local previews and prompt/alt-text pairing shared by image flows."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

log = logging.getLogger(__name__)


def image_items(data: dict[str, Any]) -> list[tuple[str, str | None]]:
    prompts = data.get("image_prompts") or [data.get("image_prompt", "")]
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 10:
        raise ValueError("image_prompts must be a list of 1-10 prompts")
    if any(not isinstance(prompt, str) or not prompt.strip() for prompt in prompts):
        raise ValueError("image_prompts must contain nonempty strings")
    alts = data.get("alt_texts")
    if alts is None:
        return [(prompt, None) for prompt in prompts]
    if not isinstance(alts, list) or len(alts) != len(prompts):
        raise ValueError("alt_texts must align with image_prompts")
    if any(not isinstance(alt, str) or not alt.strip() for alt in alts):
        raise ValueError("alt_texts must contain nonempty strings")
    return list(zip(prompts, alts, strict=True))


def save_preview(
    media: list[bytes],
    caption: str,
    *,
    suffix: str = "jpg",
    alt_texts: list[str | None] | None = None,
) -> Path:
    folder = Path("output") / "dry-run" / uuid4().hex
    folder.mkdir(parents=True)
    for index, body in enumerate(media, 1):
        (folder / f"{index:02d}.{suffix}").write_bytes(body)
    (folder / "caption.json").write_text(
        json.dumps({"caption": caption, "alt_texts": alt_texts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("DRY RUN: saved %d media preview(s) to %s", len(media), folder)
    return folder
