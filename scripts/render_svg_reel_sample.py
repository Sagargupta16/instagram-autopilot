"""Render the fixed SVG Reel samples to MP4 with real Chrome and ffmpeg, then extract frames.

Usage:
    uv run --frozen python scripts/render_svg_reel_sample.py [--name steps-cicd ...] [--no-stills]

By default renders one MP4 per pillar (steps-cicd, stat-big-number, timeline-hubble,
versus-tcp-udp, myths-space), each in
its sample look, with the pillar's licensed track baked in when the audio library has been
fetched (scripts/fetch_audio_catalog.py) and silent otherwise. When the voice model has been
fetched (scripts/fetch_voice_model.py) each sample is narrated and paced to its voice, as a
published Reel is. Writes to output/svg-reel-sample/: NAME.mp4 and NAME.svg, four PNG frames
of each MP4 (hook entrance, middle, cover frame, end card), a cover still of every sample in
every look unless --no-stills (CI renders each sample in its own job and the stills in one),
and probe.json with each MP4's ffprobe summary, audio track, narration timings and render time. Uses no credentials; the only network use is uv installing the locked narration
environment on first use. Exits non-zero when an MP4 fails the spec.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.media import audio_bake, audio_picker, narration, reel_probe, svg_video  # noqa: E402
from src.media.audio_manifest import AudioTrack  # noqa: E402
from src.media.reel_svg import Reel, compose  # noqa: E402
from src.media.svg_look import LOOKS  # noqa: E402
from src.pillar import load_config  # noqa: E402

SAMPLES = ROOT / "scripts" / "samples" / "svg_reel_scenes.json"
OUT = ROOT / "output" / "svg-reel-sample"
DEFAULT = ("steps-cicd", "stat-big-number", "timeline-hubble", "versus-tcp-udp", "myths-space")
SAMPLE_HANDLE = "@creativity.prompt"  # stand-in: published Reels read the account's live handle


def moments(reel: Reel) -> dict[str, float]:
    """Hook entrance, mid-reveal, the cover frame and the end card for any layout."""
    return {
        "1-hook": 0.4,
        "2-middle": round(reel.duration * 0.45, 2),
        "3-cover": round(reel.cover, 2),
        "4-end": round(reel.duration - 0.6, 2),
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


def themes() -> dict[str, str]:
    """Scene kind to the audio theme its pillar uses."""
    return {
        p["scene_kind"]: p["audio_theme"] for p in load_config()["pillars"] if "scene_kind" in p
    }


def track_for(kind: str) -> AudioTrack | None:
    try:
        return audio_picker.select(themes()[kind])
    except audio_picker.NoTrackAvailableError:
        return None


def render(item: dict, browser: str) -> dict:
    name = item["name"]
    video = OUT / f"{name}.mp4"
    track = track_for(item["scene"]["kind"])
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="svg-reel-sample-") as temporary:
        workdir = Path(temporary)
        voice = narration.for_scene(item["scene"], workdir)
        pace = voice.pace if voice else ()
        reel = compose(
            item["scene"],
            source_line=item["source_line"],
            look=item["look"],
            pace=pace,
            handle=SAMPLE_HANDLE,
        )
        (OUT / f"{name}.svg").write_text(reel.svg, encoding="utf-8")
        silent = svg_video.render(reel.svg, reel.duration, workdir / "silent.mp4", browser=browser)
        starts = [beat + narration.LEAD_S for beat in reel.beats]
        if voice:
            clips = list(zip(voice.clips, starts, strict=True))
            music = track.path if track else None
            final = audio_bake.mix(silent, reel.duration, voice=clips, music=music)
        else:
            final = audio_bake.bake(silent, track.path, reel.duration) if track else silent
        video.write_bytes(final.read_bytes())
    seconds = round(time.perf_counter() - started, 1)
    summary = reel_probe.verify(video, reel.duration, audio=bool(track or voice))
    summary |= {
        "render_seconds": seconds,
        "look": LOOKS[item["look"] % len(LOOKS)].name,
        "thumb_offset_ms": reel.thumb_offset_ms,
        "audio_track": track.track_id if track else None,
        "narration": [
            {"line": line, "start": round(start, 2), "seconds": spoken}
            for line, start, spoken in zip(voice.lines, starts, voice.durations, strict=True)
        ]
        if voice
        else None,
    }
    for label, at in moments(reel).items():
        extract(video, at, OUT / f"{name}-{label}.png")
    return summary


def stills(samples: dict[str, dict], browser: str) -> int:
    """The cover frame of every sample in every look, one browser shot per sample."""
    count = 0
    for name, item in samples.items():
        for index, look in enumerate(LOOKS):
            reel = compose(item["scene"], source_line=item["source_line"], look=index)
            png = svg_video.shoot(browser, reel.svg, [round(reel.cover, 2)], OUT / f"sheet-{name}")
            (frame,) = svg_video.tiles(png, 1)
            frame.save(OUT / f"still-{name}-{look.name}.png")
            png.unlink()
            png.with_suffix(".html").unlink()
            count += 1
    return count


def main() -> int:
    samples = {item["name"]: item for item in json.loads(SAMPLES.read_text("utf-8"))["scenes"]}
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--name", action="append", choices=sorted(samples))
    parser.add_argument("--no-stills", action="store_true", help="skip the cover-still gallery")
    args = parser.parse_args()
    names = args.name or list(DEFAULT)
    OUT.mkdir(parents=True, exist_ok=True)
    browser = svg_video.ensure_available()
    report = {"reels": {name: render(samples[name], browser) for name in names}}
    report["stills"] = 0 if args.no_stills else stills(samples, browser)
    (OUT / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
