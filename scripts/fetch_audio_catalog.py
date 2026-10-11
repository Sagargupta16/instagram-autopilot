"""Download the licensed audio catalog and write the manifest the audio picker reads.

Usage:
    uv run --frozen python scripts/fetch_audio_catalog.py

Each track in the tracked catalog (Mixkit Stock Music Free License: social media video posts,
no attribution; never register the tracks with a rights-management service) is saved as
assets/audio/<theme>/mixkit-<asset number>.mp3 and checked against its recorded sha256. A file
already on disk with the right hash is kept; a failed download or a hash mismatch is reported
and the track is skipped, never kept. The result is assets/audio/catalog_manifest.json, listing
only the verified files. Both the audio files and that manifest are gitignored: this public
repository never commits audio. Standard library only. Exit status 1 when any track is missing.

Requests go only to MIXKIT_MUSIC: the catalog's download_url must name a Mixkit asset number,
and the request URL, file name and manifest row are rebuilt from that number and the code's
own constants, never copied from the catalog as text.
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

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "assets" / "audio" / "catalog.json"
AUDIO_ROOT = CATALOG.parent
MANIFEST = AUDIO_ROOT / "catalog_manifest.json"
MIXKIT_MUSIC = "https://assets.mixkit.co/music/"  # the only place tracks are downloaded from
LICENSE = "Mixkit Stock Music Free License"
LICENSE_URL = "https://mixkit.co/license/#musicFree"
UA = "InstagramAutopilot/0.9 (+https://github.com/Sagargupta16/instagram-autopilot)"
THEMES = ("chill", "upbeat", "cinematic")
TRACK_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
ASSET = re.compile(re.escape(MIXKIT_MUSIC) + r"(\d{1,7})/(\d{1,7})\.mp3")
CHUNK = 1 << 16


class FetchError(Exception):
    """One track could not be downloaded or did not match its recorded hash."""


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()


def asset_number(url: object) -> int:
    """The Mixkit asset number in a catalog download URL, or FetchError for any other URL."""
    match = ASSET.fullmatch(url) if isinstance(url, str) else None
    if match is None or match[1] != match[2]:
        raise FetchError(f"refusing a download URL that is not a Mixkit music asset: {url!r}")
    return int(match[1])


def checked(track: dict[str, Any], catalog: dict[str, Any]) -> str:
    """The track's theme as the code's own constant; a malformed catalog entry is an error."""
    track_id, theme = track.get("track_id"), track.get("theme")
    if not isinstance(track_id, str) or not TRACK_ID.fullmatch(track_id):
        raise ValueError(f"catalog track_id {track_id!r} must be lowercase words and hyphens")
    if theme not in THEMES:
        raise ValueError(f"{track_id}: unsupported theme {theme!r}")
    if not isinstance(track.get("sha256"), str) or not SHA256.fullmatch(track["sha256"]):
        raise ValueError(f"{track_id}: sha256 must be 64 lowercase hex digits")
    if catalog.get("license") != LICENSE:
        raise ValueError(f"the catalog license must be {LICENSE!r}")
    return THEMES[THEMES.index(theme)]


def target_for(theme: str, number: int) -> Path:
    """mixkit-<asset number>.mp3 in the theme folder, built from code constants and an int."""
    root = AUDIO_ROOT.resolve()
    target = (root / THEMES[THEMES.index(theme)] / f"mixkit-{int(number)}.mp3").resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"mixkit-{number}: path leaves the audio library")
    return target


def download(number: int, target: Path, sha256: str, *, opener=urllib.request.urlopen) -> None:
    """Write Mixkit music asset `number` to `target` only when its bytes hash to `sha256`."""
    url = f"{MIXKIT_MUSIC}{int(number)}/{int(number)}.mp3"
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


def entry(theme: str, number: int) -> dict[str, Any]:
    """The audio_manifest.json fields the picker validates. Title, artist, listing page and
    hash stay in the tracked catalog, so the generated file holds only constants and the number."""
    return {
        "track_id": f"mixkit-{int(number)}",
        "filename": f"{THEMES[THEMES.index(theme)]}/mixkit-{int(number)}.mp3",
        "theme_tags": [THEMES[THEMES.index(theme)]],
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution_required": False,
        "attribution": "",
    }


def write_manifest(present: list[tuple[str, int]]) -> None:
    """The generated manifest at its fixed path, from validated (theme, number) pairs."""
    rows = [entry(theme, number) for theme, number in present]
    MANIFEST.write_text(json.dumps({"tracks": rows}, indent=2), "utf-8")


def fetch(*, opener=urllib.request.urlopen) -> list[str]:
    """Download what is missing, write the manifest; returns the track IDs that failed."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    present: list[tuple[str, int]] = []
    failed: list[str] = []
    for track in catalog["tracks"]:
        theme = checked(track, catalog)
        target = None
        try:
            number = asset_number(track.get("download_url"))
            target = target_for(theme, number)
            if not (target.is_file() and digest(target) == track["sha256"]):
                download(number, target, track["sha256"], opener=opener)
        except FetchError as error:
            if target is not None:
                target.unlink(missing_ok=True)
            failed.append(track["track_id"])
            sys.stderr.write(f"skip {track['track_id']}: {error}\n")
            continue
        present.append((theme, number))
    write_manifest(present)
    sys.stdout.write(f"{len(present)} of {len(catalog['tracks'])} tracks ready in {MANIFEST}\n")
    return failed


def main() -> int:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args()
    return 1 if fetch() else 0


if __name__ == "__main__":
    raise SystemExit(main())
