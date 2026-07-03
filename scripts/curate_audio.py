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
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "audio" / "audio_manifest.json"
UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
API = "https://pixabay.com/api/audio/"


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
        print(f"[{theme}] {track_id}")  # noqa: T201 -- CLI script, prints are intentional
    _write_manifest(manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", required=True, choices=["chill", "upbeat", "cinematic"])
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--api-key", default=os.environ.get("PIXABAY_KEY", ""))
    args = parser.parse_args()
    if not args.api_key:
        sys.exit("Missing --api-key or PIXABAY_KEY env var")
    curate(args.theme, args.count, args.api_key)


if __name__ == "__main__":
    main()
