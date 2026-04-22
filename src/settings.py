"""Pydantic settings loaded from .env.

Instantiated at import time -- missing required env vars raise at startup.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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

    # S3 bucket for Nova Reel video output (optional -- reels skip if empty)
    s3_video_bucket: str = ""

    # Content strategy
    niche: str = "ai_creativity_and_prompts"
    content_types: str = "tip,trick,showcase,tutorial,insight"

    @property
    def content_type_list(self) -> list[str]:
        return [t.strip() for t in self.content_types.split(",")]


settings = Settings()  # type: ignore[call-arg]
