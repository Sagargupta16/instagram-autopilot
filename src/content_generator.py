"""Generate post topics, captions, and hashtags using Bedrock Claude."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import boto3

from src.config import settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
POSTED_TOPICS_FILE = DATA_DIR / "posted_topics.json"


def _get_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _load_posted_topics() -> list[str]:
    if POSTED_TOPICS_FILE.exists():
        return json.loads(POSTED_TOPICS_FILE.read_text())
    return []


def _save_posted_topic(topic: str) -> None:
    topics = _load_posted_topics()
    topics.append(topic)
    # Keep last 500 topics to avoid infinite growth
    topics = topics[-500:]
    POSTED_TOPICS_FILE.write_text(json.dumps(topics, indent=2))


def _invoke_claude(prompt: str) -> str:
    client = _get_bedrock_client()
    response = client.invoke_model(
        modelId=settings.bedrock_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def generate_topic(content_type: str | None = None) -> dict[str, str]:
    """Generate a fresh topic that hasn't been posted before."""
    posted = _load_posted_topics()
    content_type = content_type or random.choice(settings.content_type_list)

    prompt_template = (PROMPTS_DIR / "topic_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        content_type=content_type,
        already_posted=json.dumps(posted[-50:]),  # Send recent 50 to avoid repeats
    )

    raw = _invoke_claude(prompt)
    topic_data = json.loads(raw)
    _save_posted_topic(topic_data["topic"])

    return {
        "topic": topic_data["topic"],
        "content_type": content_type,
    }


def generate_caption(topic: str, content_type: str) -> dict[str, str]:
    """Generate Instagram caption with hook, body, CTA, and hashtags."""
    prompt_template = (PROMPTS_DIR / "caption_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        topic=topic,
        content_type=content_type,
    )

    raw = _invoke_claude(prompt)
    return json.loads(raw)


def generate_carousel_slides(topic: str, num_slides: int = 7) -> list[dict[str, str]]:
    """Generate text content for each slide of a carousel post."""
    prompt_template = (PROMPTS_DIR / "carousel_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        topic=topic,
        num_slides=num_slides,
    )

    raw = _invoke_claude(prompt)
    return json.loads(raw)


def generate_reel_script(topic: str) -> dict[str, Any]:
    """Generate a short script for a Reel (voiceover text + scene descriptions)."""
    prompt_template = (PROMPTS_DIR / "reel_prompt.txt").read_text()
    prompt = prompt_template.format(
        niche=settings.niche,
        topic=topic,
    )

    raw = _invoke_claude(prompt)
    return json.loads(raw)
