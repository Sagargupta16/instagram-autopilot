"""Download the licensed audio catalog and write the manifest the audio picker reads.

Usage:
    uv run --frozen python scripts/fetch_audio_catalog.py [--catalog assets/audio/catalog.json]

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
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "assets" / "audio" / "catalog.json"
MANIFEST_NAME = "catalog_manifest.json"
UA = "InstagramAutopilot/0.9 (+https://github.com/Sagargupta16/instagram-autopilot)"
THEMES = ("chill", "upbeat", "cinematic")
CHUNK = 1 << 16


class FetchError(Exception):
    """One track could not be downloaded or did not match its recorded hash."""


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()


def download(url: str, target: Path, sha256: str, *, opener=urllib.request.urlopen) -> None:
    """Write `url` to `target` only when the bytes hash to `sha256`."""
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-HTTPS URL: {url}")
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
        if track["theme"] not in THEMES:
            raise ValueError(f"{track['track_id']}: unsupported theme {track['theme']!r}")
        target = audio_root / track["theme"] / f"{track['track_id']}.mp3"
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
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    args = parser.parse_args()
    return 1 if fetch(args.catalog, args.catalog.parent) else 0


if __name__ == "__main__":
    raise SystemExit(main())
