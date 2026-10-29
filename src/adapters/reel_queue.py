"""The private queue of finished Reels: a draft GitHub release tagged `reel-queue` whose assets
come in pairs, `<slug>.mp4` and `<slug>.json`. Draft releases and their assets are visible only
to people with push access, so a video stays private until it posts. A posted pair is renamed
`posted-<name>`, never deleted."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.settings import settings

RELEASE = "reel-queue"
POSTED = "posted-"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,80}")
MAX_HASHTAGS = 5  # Instagram's cap since 2025-12-18 (contract 26)


class QueueError(Exception):
    """The queue could not be read, or one of its entries is malformed."""


class Entry(BaseModel):
    """What `<slug>.json` holds; its facts were checked when the video was made."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    pillar: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    caption: str = Field(min_length=1)
    hashtags: str = ""
    duration_s: float = Field(ge=15, le=30)
    audio: bool
    cover_ms: int | None = Field(default=None, ge=0)
    alt_text: str = ""
    sources: list[dict[str, str]] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.caption}\n\n{self.hashtags}" if self.hashtags else self.caption

    @model_validator(mode="after")
    def fits(self) -> Entry:
        if len(self.text) > 2200:
            raise ValueError("caption and hashtags exceed Instagram's 2200 characters")
        if self.hashtags.count("#") > MAX_HASHTAGS:
            raise ValueError(f"more than {MAX_HASHTAGS} hashtags")
        if self.cover_ms is not None and self.cover_ms >= self.duration_s * 1000:
            raise ValueError("the cover frame is past the end of the video")
        return self


@dataclass(frozen=True)
class QueuedReel:
    slug: str
    entry: Entry
    video_asset: int
    meta_asset: int


class ReelQueue:
    def __init__(self, repository: str, token: str) -> None:
        if not repository or not token:
            raise QueueError("The Reel queue needs STATE_REPOSITORY and STATE_GITHUB_TOKEN")
        self.base = f"https://api.github.com/repos/{repository}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @classmethod
    def from_settings(cls) -> ReelQueue:
        return cls(settings.state_repository, settings.state_github_token)

    def _get(self, path: str, **kwargs: Any) -> requests.Response:
        response = requests.get(f"{self.base}{path}", timeout=120, **kwargs)
        response.raise_for_status()
        return response

    def _assets(self) -> list[dict[str, Any]]:
        releases = self._get("/releases", headers=self.headers, params={"per_page": 100}).json()
        drafts = [item for item in releases if item.get("draft") and item["tag_name"] == RELEASE]
        if not drafts:
            return []
        path = f"/releases/{drafts[0]['id']}/assets"
        return self._get(path, headers=self.headers, params={"per_page": 100}).json()

    def _download(self, asset: int) -> bytes:
        binary = {**self.headers, "Accept": "application/octet-stream"}
        return self._get(f"/releases/assets/{asset}", headers=binary).content

    def next_item(self, *, published: set[str]) -> QueuedReel | None:
        """The oldest complete pair whose title has no published receipt yet."""
        waiting = {
            asset["name"]: asset for asset in self._assets() if not asset["name"].startswith(POSTED)
        }
        metas = sorted(
            (asset for name, asset in waiting.items() if name.endswith(".json")),
            key=lambda asset: asset["created_at"],
        )
        for meta in metas:
            slug = meta["name"].removesuffix(".json")
            video = waiting.get(f"{slug}.mp4")
            if video is None or not SLUG.fullmatch(slug):
                continue
            try:
                entry = Entry.model_validate(json.loads(self._download(meta["id"])))
            except (ValueError, ValidationError) as error:
                raise QueueError(f"Queue entry {slug} is malformed: {error}") from error
            if entry.title not in published:
                return QueuedReel(slug, entry, video["id"], meta["id"])
        return None

    def video(self, item: QueuedReel, path: Path) -> Path:
        path.write_bytes(self._download(item.video_asset))
        return path

    def mark_posted(self, item: QueuedReel) -> None:
        for asset, suffix in ((item.video_asset, "mp4"), (item.meta_asset, "json")):
            response = requests.patch(
                f"{self.base}/releases/assets/{asset}",
                headers=self.headers,
                json={"name": f"{POSTED}{item.slug}.{suffix}"},
                timeout=30,
            )
            response.raise_for_status()
