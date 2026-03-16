from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS Bedrock
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514"
    bedrock_image_model_id: str = "amazon.titan-image-generator-v2:0"

    # Instagram
    instagram_user_id: str
    instagram_access_token: str
    meta_app_id: str = ""
    meta_app_secret: str = ""
    graph_api_version: str = "v21.0"

    # Cloudinary
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    # Content
    niche: str = "psychology_facts"
    posts_per_day: int = 2
    content_types: str = "fact,tip,carousel,reel"

    @property
    def graph_api_base(self) -> str:
        return f"https://graph.facebook.com/{self.graph_api_version}"

    @property
    def content_type_list(self) -> list[str]:
        return [t.strip() for t in self.content_types.split(",")]


settings = Settings()  # type: ignore[call-arg]
