"""Shared test fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("AWS_BEARER_TOKEN_BEDROCK", "test-token")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("COMPOSIO_API_KEY", "test-composio-key")
os.environ.setdefault("COMPOSIO_CONNECTED_ACCOUNT_ID", "test-account")
os.environ.setdefault("COMPOSIO_USER_ID", "test-user")
os.environ.setdefault("INSTAGRAM_USER_ID", "123456")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test-cloudinary-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test-cloudinary-secret")


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
def sample_caption_data() -> dict[str, Any]:
    return {
        "caption": "Here's something most people get wrong about memory...\n\nYour brain doesn't store memories like a camera.",
        "hashtags": "#psychology #memory #brain #cognitivebias #mindset",
        "x_post": "Your brain doesn't store memories like a camera. Every time you recall something, you're reconstructing it.",
        "image_prompts": [
            "A shattered mirror reflecting fragmented memories in a dark room with warm golden light rays",
            "Close-up of neural pathways firing with neon blue electricity in a dark void",
            "Hands holding a dissolving photograph, particles scattering into golden dust",
            "A brain made of cracked glass with light leaking through the fractures",
            "An empty chair in a spotlight with fading afterimages of the person who sat there",
        ],
        "video_prompt": "Slow zoom into a shattered mirror, fragments floating in darkness with golden light passing through each shard",
    }


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COMPOSIO_API_KEY", "test-composio-key")
    monkeypatch.setenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("COMPOSIO_USER_ID", "test-user")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123456")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test-cloudinary-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-cloudinary-secret")
