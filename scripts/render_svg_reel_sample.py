"""Render the fixed SVG Reel sample to MP4 with real Chrome and ffmpeg, then extract frames.

Usage:
    uv run --frozen python scripts/render_svg_reel_sample.py [--name steps-cicd]

Writes output/svg-reel-sample/NAME.mp4 and NAME.svg, four PNG frames of the MP4 (hook,
mid-steps, takeaway, final hold), one still per other sample layout, and probe.json. Uses no
credentials and makes no network requests. Exits non-zero when the MP4 fails the spec.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.media import reel_probe, svg_video  # noqa: E402
from src.media.reel_svg import compose  # noqa: E402

SAMPLES = ROOT / "scripts" / "samples" / "svg_reel_scenes.json"
OUT = ROOT / "output" / "svg-reel-sample"


def moments(duration: float) -> dict[str, float]:
    """Hook, mid-reveal, takeaway and final-hold times for any layout."""
    return {
        "1-hook": 1.2,
        "2-middle": round(duration * 0.45, 2),
        "3-takeaway": round(duration - 2.6, 2),
        "4-hold": round(duration - 0.1, 2),
    }


def extract(video: Path, seconds: float, target: Path) -> None:
    subprocess.run(
        [
            *("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(seconds)),
            *("-i", str(video), "-frames:v", "1", str(target)),
        ],
        check=True,
        timeout=60,
    )


def main() -> int:
    samples = {item["name"]: item for item in json.loads(SAMPLES.read_text("utf-8"))["scenes"]}
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--name", choices=sorted(samples), default="steps-cicd")
    chosen = samples[parser.parse_args().name]
    name = chosen["name"]
    OUT.mkdir(parents=True, exist_ok=True)
    browser = svg_video.ensure_available()
    reel = compose(chosen["scene"], source_line=chosen["source_line"])
    (OUT / f"{name}.svg").write_text(reel.svg, encoding="utf-8")
    video = OUT / f"{name}.mp4"
    started = time.perf_counter()
    svg_video.render(reel.svg, reel.duration, video, browser=browser)
    seconds = round(time.perf_counter() - started, 1)
    summary = reel_probe.verify(video, reel.duration, audio=False)
    summary["render_seconds"] = seconds
    (OUT / "probe.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for label, at in moments(reel.duration).items():
        extract(video, at, OUT / f"{name}-{label}.png")
    for other_name, item in samples.items():
        if other_name == name:
            continue
        other = compose(item["scene"], source_line=item["source_line"])
        times = [round(other.duration * 0.45, 2), round(other.duration - 0.1, 2)]
        png = svg_video.shoot(browser, other.svg, times, OUT / f"still-{other_name}")
        for frame, label in zip(svg_video.tiles(png, len(times)), ("middle", "hold"), strict=True):
            frame.save(OUT / f"still-{other_name}-{label}.png")
        png.unlink()
        png.with_suffix(".html").unlink()
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
