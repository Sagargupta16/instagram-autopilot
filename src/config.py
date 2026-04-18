from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS Bedrock (bearer token auth)
    aws_bearer_token_bedrock: str
    aws_region: str = "us-east-1"

    # Composio SDK (handles Instagram + X/Twitter)
    composio_api_key: str

    # imgbb (free image hosting -- Instagram needs public URLs)
    imgbb_api_key: str

    # S3 bucket for Nova Reel video output
    s3_video_bucket: str = ""

    # Content
    niche: str = "psychology_facts"
    content_types: str = "fact,tip"

    @property
    def content_type_list(self) -> list[str]:
        return [t.strip() for t in self.content_types.split(",")]


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text())


def get_todays_pillar(config: dict[str, Any]) -> dict[str, Any] | None:
    today = datetime.now(UTC).strftime("%A").lower()
    for pillar in config["pillars"]:
        if today in pillar["days"]:
            return pillar
    return None


settings = Settings()  # type: ignore[call-arg]
