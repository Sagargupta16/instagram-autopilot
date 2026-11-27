"""The private queue of finished Reels: a draft GitHub release tagged `reel-queue` whose assets
come in pairs, `<slug>.mp4` and `<slug>.json`. Draft releases and their assets are visible only
to people with push access, so a video stays private until it posts. A posted pair is renamed
`posted-<name>`, and a pair set aside `<name>.failed-<stamp>` (contract 32); never deleted."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from requests.exceptions import RequestException

from src.config.settings import settings

RELEASE = "reel-queue"
POSTED = "posted-"
FAILED = ".failed-"
STAMP = "%Y%m%dT%H%MZ"  # UTC to the minute, e.g. 20261127T0432Z
SET_ASIDE = re.compile(r"(?P<slug>.+)\.(?:mp4|json)\.failed-(?P<stamp>\d{8}T\d{4}Z)(?P<n>-\d+)?")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,80}")
MAX_HASHTAGS = 5  # Instagram's cap since 2025-12-18 (contract 26)
# Instagram recommends Reels to non-followers up to 3 minutes long (creators FAQ); the owner
# lifted the old 30 s ceiling for queued videos on 2026-11-15 ("30 second is not hard rule").
MAX_S = 180


class QueueError(Exception):
    """The queue could not be read, or one of its entries is malformed."""


class BadPair(QueueError):
    """A pair that cannot post because of its own files, judged on bytes that arrived whole:
    `video_asset` and `meta_asset` are the asset ids that were judged."""

    def __init__(self, slug: str, video_asset: int, meta_asset: int, reason: str) -> None:
        super().__init__(f"Queued pair {slug} cannot post: {reason}")
        self.slug, self.reason = slug, reason
        self.video_asset, self.meta_asset = video_asset, meta_asset


def _whole(name: str, size: int | None, digest: str | None, body: bytes) -> bool:
    """True when `body` is provably the whole listed asset (its size, and its sha256 when
    GitHub lists one); a download that contradicts the listing raises QueueError, as a network
    fault does. Without a listed size nothing is proven, so nothing is judged on the bytes."""
    if size is None:
        return False
    listed = digest if (digest or "").startswith("sha256:") else None  # other algorithms: unread
    if len(body) != size or listed not in {None, "sha256:" + hashlib.sha256(body).hexdigest()}:
        raise QueueError(f"Queue asset {name} did not arrive whole ({len(body)} of {size} bytes)")
    return True


def _field(loc: tuple[int | str, ...]) -> str:
    """The field of Entry a fault sits in; a key the entry made up is never named."""
    return str(loc[0]) if loc and loc[0] in Entry.model_fields else "entry"


def _why(error: Exception) -> str:
    """Why an entry is bad, without its own text: run summaries are public, the queue is not."""
    if not isinstance(error, ValidationError):
        return "its JSON does not parse"
    fields = (f"{_field(item['loc'])}: {item['msg']}" for item in error.errors())
    return ("its JSON does not validate: " + "; ".join(fields))[:300]


class Entry(BaseModel):
    """What `<slug>.json` holds; its facts were checked when the video was made."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    pillar: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    caption: str = Field(min_length=1)
    hashtags: str = ""
    duration_s: float = Field(ge=15, le=MAX_S)
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
    video_size: int | None  # as listed, so the download can be proven whole
    video_digest: str | None


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
            # Never read as an empty queue: a token that cannot see drafts would post nothing.
            raise QueueError(f"The draft release {RELEASE} is missing or not visible to the token")
        path = f"/releases/{drafts[0]['id']}/assets"
        # GitHub lists 100 assets a page, sorted by name, and posted pairs are kept: read to the
        # last page, or every name that sorts past the first hundred is invisible.
        assets: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {"per_page": 100, "page": page}
            batch = self._get(path, headers=self.headers, params=params).json()
            assets.extend(batch)
            if len(batch) < 100:
                return assets
            page += 1

    def _download(self, asset: int) -> bytes:
        binary = {**self.headers, "Accept": "application/octet-stream"}
        return self._get(f"/releases/assets/{asset}", headers=binary).content

    def next_item(
        self, *, published: set[str], slug: str | None = None, exclude: frozenset[str] = frozenset()
    ) -> QueuedReel | None:
        """The oldest complete pair whose title has no published receipt yet; with slug, only
        that pair, so a timely video can go before the rest of the queue. Slugs in `exclude`
        (set aside in this run) are passed over. A JSON that arrived whole and does not parse
        or validate raises BadPair."""
        waiting = {
            asset["name"]: asset for asset in self._assets() if not asset["name"].startswith(POSTED)
        }
        metas = sorted(
            (asset for name, asset in waiting.items() if name.endswith(".json")),
            key=lambda asset: asset["created_at"],
        )
        if slug is not None:
            metas = [asset for asset in metas if asset["name"] == f"{slug}.json"]
        for meta in metas:
            slug = meta["name"].removesuffix(".json")
            video = waiting.get(f"{slug}.mp4")
            if video is None or not SLUG.fullmatch(slug) or slug in exclude:
                continue
            body = self._download(meta["id"])
            whole = _whole(meta["name"], meta.get("size"), meta.get("digest"), body)
            try:
                entry = Entry.model_validate(json.loads(body))
            except (ValueError, ValidationError, RecursionError) as error:  # too deep: no parse
                if whole:
                    raise BadPair(slug, video["id"], meta["id"], _why(error)) from error
                raise QueueError(f"Queue entry {slug} is malformed: {error}") from error
            if entry.title not in published:
                size, digest = video.get("size"), video.get("digest")
                return QueuedReel(slug, entry, video["id"], meta["id"], size, digest)
        return None

    def video(self, item: QueuedReel, path: Path) -> Path:
        """Save the video; a download that contradicts its listed size or digest raises."""
        body = self._download(item.video_asset)
        _whole(f"{item.slug}.mp4", item.video_size, item.video_digest, body)
        path.write_bytes(body)
        return path

    def _rename(self, asset: int, name: str) -> None:
        response = requests.patch(
            f"{self.base}/releases/assets/{asset}",
            headers=self.headers,
            json={"name": name},
            timeout=30,
        )
        response.raise_for_status()

    def mark_posted(self, item: QueuedReel) -> None:
        self._rename(item.video_asset, f"{POSTED}{item.slug}.mp4")
        self._rename(item.meta_asset, f"{POSTED}{item.slug}.json")

    def set_aside(self, bad: BadPair, now: datetime) -> str:
        """Rename the two judged assets, by id, to `<name>.failed-<stamp>`, never deleting them,
        and return that suffix; `-2`, `-3` keep both new names free in the current listing."""
        names = {asset["name"] for asset in self._assets()}
        base = suffix = FAILED + now.astimezone(UTC).strftime(STAMP)
        count = 1
        while {f"{bad.slug}.mp4{suffix}", f"{bad.slug}.json{suffix}"} & names:
            count += 1
            suffix = f"{base}-{count}"
        try:
            self._rename(bad.video_asset, f"{bad.slug}.mp4{suffix}")
            self._rename(bad.meta_asset, f"{bad.slug}.json{suffix}")
        except RequestException as error:
            self._undo(bad, suffix, error)
        return suffix

    def _undo(self, bad: BadPair, suffix: str, error: RequestException) -> None:
        """A rename failed, and a lost response can hide one that landed: read where the two
        judged assets stand now and give each renamed one its name back, so the pair is never
        left half aside without a word. Always raises."""
        try:
            now = {asset["id"]: asset["name"] for asset in self._assets()}
            for asset, name in ((bad.video_asset, "mp4"), (bad.meta_asset, "json")):
                if now.get(asset) == f"{bad.slug}.{name}{suffix}":
                    self._rename(asset, f"{bad.slug}.{name}")
        except RequestException:
            raise QueueError(
                f"Queued pair {bad.slug} may be half set aside as {suffix}: look at the names "
                f"of {bad.slug}.mp4 and {bad.slug}.json in the release"
            ) from error
        raise error

    def set_aside_since(self, moment: datetime | None) -> int:
        """Pairs whose `.failed-<stamp>` is at or after `moment`'s minute; every one when None."""
        floor = moment and moment.astimezone(UTC).replace(second=0, microsecond=0)
        pairs = set()
        for asset in self._assets():
            match = SET_ASIDE.fullmatch(asset["name"])
            if match is None:
                continue
            stamp = datetime.strptime(match["stamp"], STAMP).replace(tzinfo=UTC)
            if floor is None or stamp >= floor:
                pairs.add((match["slug"], match["stamp"], match["n"]))
        return len(pairs)
