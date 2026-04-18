"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture()
def sample_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    return json.loads(config_path.read_text())


@pytest.fixture()
def sample_pillar() -> dict[str, Any]:
    return {
        "id": "cognitive_biases",
        "label": "Cognitive Biases",
        "days": ["monday", "thursday"],
        "hashtags": ["#psychology", "#cognitivebias", "#mindset"],
        "image_style": "PHOTOREALISM",
        "content_format": "image",
    }


@pytest.fixture()
def sample_persona() -> dict[str, Any]:
    return {
        "name": "Psychology Insider",
        "tone": "conversational, authoritative but approachable",
        "cta_styles": ["save this for later", "share with someone who needs this"],
    }


@pytest.fixture()
def sample_caption_data() -> dict[str, str]:
    return {
        "caption": "Here's something most people get wrong about memory...\n\nYour brain doesn't store memories like a camera.",
        "hashtags": "#psychology #memory #brain #cognitivebias #mindset",
        "x_post": "Your brain doesn't store memories like a camera. Every time you recall something, you're reconstructing it.",
        "image_prompt": "A shattered mirror reflecting fragmented memories in a dark room with warm golden light rays",
        "video_prompt": "Slow zoom into a shattered mirror, fragments floating in darkness with golden light passing through each shard",
    }


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    monkeypatch.setenv("COMPOSIO_API_KEY", "test-composio-key")
    monkeypatch.setenv("COMPOSIO_ENTITY_ID", "test-entity")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123456")
    monkeypatch.setenv("IMGBB_API_KEY", "test-imgbb-key")
