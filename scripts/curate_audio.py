"""One-off Pixabay Music curation. Not run in CI.

Usage:
    export PIXABAY_KEY=xxx  # from https://pixabay.com/api/docs/
    python scripts/curate_audio.py --theme chill --count 10
    python scripts/curate_audio.py --theme upbeat --count 10
    python scripts/curate_audio.py --theme cinematic --count 10

Filters to plays <100k, duration >=60s. Downloads to
assets/audio/{theme}/{slug}.mp3 and appends manifest entries. The
Pixabay Content License allows commercial use without attribution.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
# Direct script execution puts scripts/, rather than the repository, on sys.path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.media.audio_manifest import THEMES, validate_track  # noqa: E402

MANIFEST = ROOT / "assets" / "audio" / "audio_manifest.json"
UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
API = "https://pixabay.com/api/audio/"


def _validated_source(candidate: Path) -> Path:
    """Confine an operator-supplied manifest path to the repository or working directory.

    The CLI is the only untrusted entry point for this path, so traversal is rejected
    here rather than inside import_legacy(), which callers already invoke with paths
    they control.
    """
    resolved = candidate.expanduser().resolve(strict=True)
    allowed = (ROOT, Path.cwd().resolve())
    if not any(resolved.is_relative_to(base) for base in allowed):
        raise ValueError("Legacy manifest must sit inside the repository or working directory")
    if not resolved.is_file():
        raise ValueError("Legacy manifest must be a regular file")
    return resolved


def import_legacy(
    source: Path, destination: Path = MANIFEST, audio_root: Path = ROOT / "assets" / "audio"
) -> None:
    """Explicitly import existing local assets; never download or modify the source.

    Operator input reaches this function through _validated_source(); direct callers
    are responsible for passing a path they already trust.
    """
    rows = json.loads(source.read_text(encoding="utf-8"))  # NOSONAR -- path confined by caller
    if not isinstance(rows, list):
        raise ValueError("Legacy manifest must be a list")
    if source.resolve() == destination.resolve():
        raise ValueError("Import destination must differ from the legacy source")
    tracks = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Legacy track must be an object")
        duration = row.get("duration_s")
        if (
            not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise ValueError("Legacy duration must be positive")
        license_name = row.get("license")
        source_url = row.get("source")
        if not isinstance(license_name, str) or not license_name.strip():
            raise ValueError("Legacy license is required")
        if not isinstance(source_url, str) or urlsplit(source_url).scheme != "https":
            raise ValueError("Legacy source must be an HTTPS URL")
        filename = row.get("file")
        track = {
            "track_id": "legacy-" + sha256(str(filename).encode()).hexdigest()[:16],
            "filename": filename,
            "theme_tags": [row.get("theme")],
            "license": row.get("license", ""),
            "attribution_required": True,
            "attribution": row.get("attribution", ""),
            "source_url": row.get("source", ""),
            "duration_s": duration,
        }
        validate_track(track, audio_root)
        tracks.append(track)
    existing = (
        json.loads(destination.read_text(encoding="utf-8"))
        if destination.exists()
        else {"tracks": []}
    )
    merged = {track["track_id"]: track for track in existing["tracks"]}
    merged.update({track["track_id"]: track for track in tracks})
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"tracks": list(merged.values())}, stream, indent=2)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:50] or "track"


def _load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"tracks": []}
    return json.loads(MANIFEST.read_text())


def _write_manifest(m: dict) -> None:
    # NOSONAR python:S6931 -- MANIFEST is a module-level constant derived
    # from __file__, not user input. Not a path-injection surface.
    m.pop("_notes", None)
    MANIFEST.write_text(json.dumps(m, indent=2))  # NOSONAR


def curate(theme: str, count: int, api_key: str) -> None:
    if theme not in THEMES or not 1 <= count <= 50:
        raise ValueError("Choose a supported theme and a count between 1 and 50")
    theme_dir = ROOT / "assets" / "audio" / theme
    theme_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        API,
        params={
            "key": api_key,
            "q": theme,
            "min_duration": 60,
            "order": "latest",
            "per_page": 50,
        },
        headers={"User-Agent": UA},
        timeout=30,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    manifest = _load_manifest()
    picked = 0
    for hit in hits:
        if picked >= count:
            break
        if hit.get("plays", 0) > 100_000:
            continue
        slug = _slugify(hit.get("title", "track"))
        track_id = f"{theme}-{slug}-{hit['id']}"
        filename = f"{theme}/{slug}-{hit['id']}.mp3"
        target = ROOT / "assets" / "audio" / filename
        if target.exists():
            continue
        mp3 = requests.get(hit["audio"], headers={"User-Agent": UA}, timeout=60)
        mp3.raise_for_status()
        target.write_bytes(mp3.content)
        manifest["tracks"].append(
            {
                "track_id": track_id,
                "filename": filename,
                "theme_tags": [theme],
                "license": "Pixabay Content License",
                "attribution_required": False,
                "source_url": f"https://pixabay.com/music/-{hit['id']}",
                "duration_s": hit.get("duration", 0),
                "plays_at_curation": hit.get("plays", 0),
                "curated_at": datetime.now(UTC).date().isoformat(),
            }
        )
        picked += 1
        print(f"[{theme}] {track_id}")  # noqa: T201  # NOSONAR -- CLI script, prints intentional
    _write_manifest(manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--theme", choices=THEMES)
    mode.add_argument("--import-legacy", type=Path, metavar="MANIFEST")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--api-key", default=os.environ.get("PIXABAY_KEY", ""))
    args = parser.parse_args()
    if args.import_legacy:
        import_legacy(_validated_source(args.import_legacy))
        return
    if not args.api_key:
        sys.exit("Missing --api-key or PIXABAY_KEY env var")
    curate(args.theme, args.count, args.api_key)


if __name__ == "__main__":
    main()
