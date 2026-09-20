"""Pydantic settings loaded from .env.

Instantiated at import time -- missing required env vars raise at startup.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    # AWS Bedrock (bearer token auth)
    aws_bearer_token_bedrock: str
    aws_region: str = "us-east-1"

    # Composio (Instagram publishing via REST API)
    composio_api_key: str
    composio_connected_account_id: str = ""
    composio_user_id: str = "default"
    instagram_user_id: str = ""

    # Cloudinary (image hosting -- Meta trusts res.cloudinary.com, blocks imgbb)
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    # S3 output for Luma; its IAM credentials are separate from Bedrock bearer auth.
    s3_video_bucket: str = ""
    allow_silent_reels: bool = False

    # Guardian Open Platform (dev-tier "test" key works without registration)
    guardian_api_key: str = ""

    # Meta Graph API (Places search -- direct call, not via Composio)
    meta_user_access_token: str = ""
    meta_graph_api_version: str = "v21.0"

    # Content strategy (wide lifestyle: travel, food, fitness, entertainment, tech, lifestyle)
    niche: str = "wide_lifestyle"
    content_types: str = "tip,story,scene,guide,insight,list,how-to,showcase"

    # Legacy compatibility setting; current scheduling uses config.json cadence.
    post_jitter_max_minutes: int = 180
    state_backend: Literal["local", "github"] = "local"
    state_repository: str = ""
    state_github_token: str = ""
    state_branch: str = "autopilot-state"
    state_path: str = "data/publication_state.json"

    @property
    def content_type_list(self) -> list[str]:
        return [t.strip() for t in self.content_types.split(",") if t.strip()] or ["guide"]


settings = Settings(_env_file=os.environ.get("AUTOPILOT_ENV_FILE", ".env"))  # type: ignore[call-arg]
