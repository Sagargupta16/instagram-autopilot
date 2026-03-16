"""Publish content to Instagram using the Graph API."""

from __future__ import annotations

import time

import requests

from src.config import settings


class InstagramPublisher:
    def __init__(self) -> None:
        self.base_url = settings.graph_api_base
        self.user_id = settings.instagram_user_id
        self.access_token = settings.instagram_access_token

    def _api_url(self, path: str) -> str:
        return f"{self.base_url}/{path}"

    def _default_params(self) -> dict[str, str]:
        return {"access_token": self.access_token}

    def publish_image(self, image_url: str, caption: str) -> str:
        """Publish a single image post. Returns the media ID."""
        # Step 1: Create media container
        resp = requests.post(
            self._api_url(f"{self.user_id}/media"),
            data={
                **self._default_params(),
                "image_url": image_url,
                "caption": caption,
            },
            timeout=30,
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]

        # Step 2: Publish
        return self._publish_container(creation_id)

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        """Publish a carousel post (2-10 images). Returns the media ID."""
        # Step 1: Create individual media containers
        children_ids: list[str] = []
        for url in image_urls:
            resp = requests.post(
                self._api_url(f"{self.user_id}/media"),
                data={
                    **self._default_params(),
                    "image_url": url,
                    "is_carousel_item": "true",
                },
                timeout=30,
            )
            resp.raise_for_status()
            children_ids.append(resp.json()["id"])

        # Step 2: Create carousel container
        resp = requests.post(
            self._api_url(f"{self.user_id}/media"),
            data={
                **self._default_params(),
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
            },
            timeout=30,
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]

        # Step 3: Publish
        return self._publish_container(creation_id)

    def publish_reel(self, video_url: str, caption: str) -> str:
        """Publish a Reel (video post). Returns the media ID."""
        # Step 1: Create media container
        resp = requests.post(
            self._api_url(f"{self.user_id}/media"),
            data={
                **self._default_params(),
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
            },
            timeout=30,
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]

        # Step 2: Wait for video processing
        self._wait_for_processing(creation_id)

        # Step 3: Publish
        return self._publish_container(creation_id)

    def _publish_container(self, creation_id: str) -> str:
        """Publish a media container. Returns the published media ID."""
        resp = requests.post(
            self._api_url(f"{self.user_id}/media_publish"),
            data={
                **self._default_params(),
                "creation_id": creation_id,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_for_processing(self, creation_id: str, max_wait: int = 120) -> None:
        """Poll until video processing is complete."""
        start = time.time()
        while time.time() - start < max_wait:
            resp = requests.get(
                self._api_url(creation_id),
                params={
                    **self._default_params(),
                    "fields": "status_code",
                },
                timeout=15,
            )
            resp.raise_for_status()
            status = resp.json().get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError(f"Video processing failed for {creation_id}")
            time.sleep(5)
        raise TimeoutError(f"Video processing timed out after {max_wait}s")

    def refresh_token(self) -> str:
        """Exchange current long-lived token for a new one (call before expiry)."""
        resp = requests.get(
            self._api_url("oauth/access_token"),
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": self.access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        new_token = resp.json()["access_token"]
        return new_token
