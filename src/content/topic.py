"""Generate daily post topics -- grounded in live trends, deduped against history."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.adapters.bedrock import invoke_claude
from src.content.dedup import load_posted_topics
from src.content.grounding import evidence_text, numbers
from src.content.schemas import TopicChoice
from src.content.sources import normalize_topic
from src.content.trends import fetch_trending_topics
from src.content.validation import generate_validated
from src.pillar import load_config, scene_kind
from src.settings import settings

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "topic.txt"
FORMATS_DIR = PROMPT_PATH.parent / "formats"
NUMERIC_FORMATS = {"stat", "timeline"}


def _check_evidence(kind: str | None, selected: list[dict]) -> None:
    """Stat and timeline Reels can only show numbers that the chosen records contain."""
    if kind == "stat" and not any(numbers(evidence_text([record])) for record in selected):
        raise ValueError("a stat Reel needs a selected source whose title or excerpt has a number")
    if kind == "timeline" and len(set(numbers(evidence_text(selected)))) < 4:
        raise ValueError("a timeline Reel needs selected sources that state at least four dates")


def generate_topic(pillar: dict[str, Any], content_type: str) -> str:
    """Compatibility wrapper returning the selected topic as a string."""
    return generate_topic_brief(pillar, content_type)["topic"]


def generate_topic_brief(pillar: dict[str, Any], content_type: str) -> dict:
    """Return topic and selected original source records, never model-authored metadata."""
    posted = load_posted_topics()

    try:
        trends = fetch_trending_topics(limit=15, pillar=pillar, include_metadata=True)
    except Exception as e:
        log.warning("Trend fetch failed; using an evergreen topic: %s", e)
        trends = []

    kind = scene_kind(pillar)
    if kind in NUMERIC_FORMATS and not any(numbers(evidence_text([record])) for record in trends):
        raise ValueError(f"No source evidence with numbers or dates for a {kind} Reel today")
    brief = (FORMATS_DIR / f"{kind or 'carousel'}.topic.txt").read_text(encoding="utf-8")
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        niche=settings.niche,
        pillar=pillar["label"],
        content_type=content_type,
        format_brief=brief.strip(),
        already_posted=json.dumps(posted[-50:]),
        trending_topics=json.dumps(trends, ensure_ascii=False),
    )

    config = load_config()
    seen = {normalize_topic(topic) for topic in posted}

    def validate(raw: object) -> TopicChoice:
        choice = TopicChoice.model_validate(raw)
        if normalize_topic(choice.topic) in seen:
            raise ValueError("duplicate topic: choose different wording and a genuinely new angle")
        if any(index < 0 or index >= len(trends) for index in choice.source_indices):
            raise ValueError("source_indices must reference supplied evidence, starting at zero")
        if len(set(choice.source_indices)) != len(choice.source_indices):
            raise ValueError("source_indices must be unique")
        _check_evidence(kind, [trends[index] for index in choice.source_indices])
        return choice

    choice = generate_validated(
        prompt, lambda text: invoke_claude(config["models"]["text"], text), validate
    )

    log.info("Generated topic: %s", choice.topic)
    return {
        "topic": choice.topic,
        "sources": [dict(trends[index]) for index in choice.source_indices],
    }
