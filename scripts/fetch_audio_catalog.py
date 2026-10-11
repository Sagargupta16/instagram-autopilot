"""Download the licensed audio catalog and write the manifest the audio picker reads.

Usage:
    uv run --frozen python scripts/fetch_audio_catalog.py

Each track in the tracked catalog (Mixkit Stock Music Free License: social media video posts,
no attribution; never register the tracks with a rights-management service) is saved as
assets/audio/<theme>/<track_id>.mp3 and checked against its recorded sha256. A file already
on disk with the right hash is kept; a failed download or a hash mismatch is reported and the
track is skipped, never kept. The result is assets/audio/catalog_manifest.json, listing only the
verified files. Both the audio files and that manifest are gitignored: this public repository
never commits audio. Standard library only. Exit status 1 when any track is missing afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "assets" / "audio" / "catalog.json"
MANIFEST_NAME = "catalog_manifest.json"
UA = "InstagramAutopilot/0.9 (+https://github.com/Sagargupta16/instagram-autopilot)"
THEMES = ("chill", "upbeat", "cinematic")
HOSTS = frozenset({"assets.mixkit.co"})  # the only place tracks are downloaded from
TRACK_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 16


class FetchError(Exception):
    """One track could not be downloaded or did not match its recorded hash."""


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in HOSTS and not parts.username


def target_for(track: dict[str, Any], audio_root: Path) -> Path:
    """The track's file inside the audio library; a malformed catalog entry is an error."""
    track_id, theme = track.get("track_id"), track.get("theme")
    if not isinstance(track_id, str) or not TRACK_ID.fullmatch(track_id):
        raise ValueError(f"catalog track_id {track_id!r} must be lowercase words and hyphens")
    if theme not in THEMES:
        raise ValueError(f"{track_id}: unsupported theme {theme!r}")
    if not isinstance(track.get("sha256"), str) or not SHA256.fullmatch(track["sha256"]):
        raise ValueError(f"{track_id}: sha256 must be 64 lowercase hex digits")
    root = audio_root.resolve()
    target = (root / theme / f"{track_id}.mp3").resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"{track_id}: path leaves the audio library")
    return target


def download(url: str, target: Path, sha256: str, *, opener=urllib.request.urlopen) -> None:
    """Write `url` to `target` only when the bytes hash to `sha256`."""
    if not allowed(url):
        raise FetchError(f"refusing a URL outside https://{', '.join(sorted(HOSTS))}: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix=".part")
    try:
        sha = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as stream, opener(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            kind = response.headers.get("Content-Type", "")
            if status != 200 or not kind.startswith("audio/"):
                raise FetchError(f"{url} returned {status} {kind or 'without a content type'}")
            while block := response.read(CHUNK):
                sha.update(block)
                stream.write(block)
        if sha.hexdigest() != sha256:
            raise FetchError(f"{url} does not match its recorded sha256")
        Path(temporary).replace(target)
    except OSError as error:
        raise FetchError(f"{url} failed: {type(error).__name__}") from error
    finally:
        Path(temporary).unlink(missing_ok=True)


def entry(track: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """The audio_manifest.json fields the picker validates, plus provenance."""
    return {
        "track_id": track["track_id"],
        "filename": f"{track['theme']}/{track['track_id']}.mp3",
        "theme_tags": [track["theme"]],
        "title": track["title"],
        "artist": track["artist"],
        "license": catalog["license"],
        "license_url": catalog["license_url"],
        "attribution_required": False,
        "attribution": "",
        "source_url": track["page_url"],
        "duration_s": track["duration_s"],
        "sha256": track["sha256"],
    }


def fetch(catalog_path: Path, audio_root: Path, *, opener=urllib.request.urlopen) -> list[str]:
    """Download what is missing, write the manifest; returns the track IDs that failed."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    present, failed = [], []
    for track in catalog["tracks"]:
        target = target_for(track, audio_root)
        try:
            if not (target.is_file() and digest(target) == track["sha256"]):
                download(track["download_url"], target, track["sha256"], opener=opener)
        except FetchError as error:
            target.unlink(missing_ok=True)
            failed.append(track["track_id"])
            sys.stderr.write(f"skip {track['track_id']}: {error}\n")
            continue
        present.append(entry(track, catalog))
    manifest = audio_root / MANIFEST_NAME
    manifest.write_text(json.dumps({"tracks": present}, ensure_ascii=False, indent=2), "utf-8")
    sys.stdout.write(f"{len(present)} of {len(catalog['tracks'])} tracks ready in {manifest}\n")
    return failed


def main() -> int:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args()
    return 1 if fetch(CATALOG, CATALOG.parent) else 0


if __name__ == "__main__":
    raise SystemExit(main())
