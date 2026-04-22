"""Generate topics, captions, and X posts using AWS Bedrock Claude."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import requests

from src.config import load_config, settings
from src.generator.trends import fetch_trending_topics

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
POSTED_TOPICS_FILE = DATA_DIR / "posted_topics.json"

BEDROCK_INVOKE_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"


def _invoke_bedrock(prompt: str) -> str:
    """Call Bedrock Claude via bearer token and return the text response."""
    config = load_config()
    url = BEDROCK_INVOKE_URL.format(
        region=settings.aws_region,
        model=config["models"]["text"],
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
    }
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(url, json=body, headers=headers, timeout=60)
    if not resp.ok:
        log.error("Bedrock %s returned %s: %s", resp.status_code, resp.reason, resp.text)
        resp.raise_for_status()
    result = resp.json()
    return result["content"][0]["text"]


def _extract_json(raw: str) -> Any:
    """Extract JSON from Bedrock response, handling markdown code fences."""
    raw = raw.strip()
    # Strip ```json ... ``` wrapper if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)


# -- Topic dedup tracking --


def _load_posted_topics() -> list[str]:
    if POSTED_TOPICS_FILE.exists():
        return json.loads(POSTED_TOPICS_FILE.read_text())
    return []


def _save_posted_topic(topic: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    topics = _load_posted_topics()
    topics.append(topic)
    topics = topics[-500:]
    POSTED_TOPICS_FILE.write_text(json.dumps(topics, indent=2))


# -- Public API --


def generate_topic(pillar: dict[str, Any], content_type: str) -> str:
    """Generate a fresh topic that hasn't been posted before.

    Grounds the topic in current trends by fetching recent headlines from
    Hacker News and Reddit before asking Claude to pick an angle.
    """
    posted = _load_posted_topics()

    try:
        trends = fetch_trending_topics(limit=15)
    except Exception as e:
        log.warning("Trend fetch failed entirely, falling back to untethered generation: %s", e)
        trends = []

    prompt_template = (PROMPTS_DIR / "topic_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        pillar=pillar["label"],
        content_type=content_type,
        already_posted=json.dumps(posted[-50:]),
        trending_topics=json.dumps(trends) if trends else "[]",
    )

    raw = _invoke_bedrock(prompt)
    topic_data = _extract_json(raw)
    topic = topic_data["topic"]

    _save_posted_topic(topic)
    log.info("Generated topic: %s", topic)
    return topic


def generate_caption(
    topic: str,
    pillar: dict[str, Any],
    persona: dict[str, Any],
) -> dict[str, Any]:
    """Generate Instagram caption, X post, and carousel image prompts."""
    prompt_template = (PROMPTS_DIR / "caption_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        pillar=pillar["label"],
        topic=topic,
        tone=persona["tone"],
        image_style=pillar.get("image_style", "PHOTOREALISM"),
        pillar_hashtags=" ".join(pillar["hashtags"]),
    )

    raw = _invoke_bedrock(prompt)
    data = _extract_json(raw)
    slide_count = len(data.get("image_prompts", []))
    log.info(
        "Generated caption (%d chars), X post (%d chars), %d image prompts",
        len(data["caption"]),
        len(data["x_post"]),
        slide_count,
    )
    return data
