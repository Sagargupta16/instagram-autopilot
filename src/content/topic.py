"""Generate daily post topics -- grounded in live trends, deduped against history."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.adapters.bedrock import extract_json, invoke_claude
from src.content.dedup import load_posted_topics, save_posted_topic
from src.content.trends import fetch_trending_topics
from src.pillar import load_config
from src.settings import settings

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "topic.txt"


def generate_topic(pillar: dict[str, Any], content_type: str) -> str:
    """Generate a fresh topic grounded in HN/Reddit trends, deduped against history."""
    posted = load_posted_topics()

    try:
        trends = fetch_trending_topics(limit=15)
    except Exception as e:
        log.warning("Trend fetch failed, falling back to untethered generation: %s", e)
        trends = []

    prompt = PROMPT_PATH.read_text().format(
        niche=settings.niche,
        pillar=pillar["label"],
        content_type=content_type,
        already_posted=json.dumps(posted[-50:]),
        trending_topics=json.dumps(trends) if trends else "[]",
    )

    config = load_config()
    raw = invoke_claude(config["models"]["text"], prompt)
    topic = extract_json(raw)["topic"]

    save_posted_topic(topic)
    log.info("Generated topic: %s", topic)
    return topic
