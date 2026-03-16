"""Upload media to Cloudinary and return public URLs."""

from __future__ import annotations

from pathlib import Path

import cloudinary
import cloudinary.uploader

from src.config import settings


def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def upload_image(image_path: Path, folder: str = "instagram-autopilot") -> str:
    """Upload an image to Cloudinary. Returns the public URL."""
    _configure_cloudinary()
    result = cloudinary.uploader.upload(
        str(image_path),
        folder=folder,
        resource_type="image",
    )
    return result["secure_url"]


def upload_video(video_path: Path, folder: str = "instagram-autopilot") -> str:
    """Upload a video to Cloudinary. Returns the public URL."""
    _configure_cloudinary()
    result = cloudinary.uploader.upload(
        str(video_path),
        folder=folder,
        resource_type="video",
    )
    return result["secure_url"]


def upload_images(image_paths: list[Path], folder: str = "instagram-autopilot") -> list[str]:
    """Upload multiple images. Returns list of public URLs."""
    return [upload_image(p, folder) for p in image_paths]
