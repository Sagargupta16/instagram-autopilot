"""SVG to MP4: frame clock, batch pages, tool commands, tiling, encoding and the ffprobe gate."""

from __future__ import annotations

import copy
import json
import shutil
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path

import pytest
from PIL import Image

from src.media.svg.reel_svg import compose
from src.media.video import reel_probe, svg_video
from src.media.video.svg_video import SvgVideoError

SAMPLES = Path(__file__).resolve().parents[3] / "scripts" / "samples" / "svg_reel_scenes.json"
W, H = svg_video.WIDTH, svg_video.HEIGHT
MARK = (255, 255, 255)


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def parse(page: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = Tags()
    parser.feed(page)
    return parser.tags


def sheet(path: Path, colors: list[tuple[int, int, int]], *, marked: bool = True) -> Path:
    """A 4x2 grid PNG whose tiles are flat colors, each with a small white mark."""
    image = Image.new("RGB", (svg_video.COLS * W, svg_video.ROWS * H))
    for index, color in enumerate(colors):
        x, y = (index % svg_video.COLS) * W, (index // svg_video.COLS) * H
        image.paste(color, (x, y, x + W, y + H))
        if marked:
            image.paste(MARK, (x + 10, y + 10, x + 20, y + 20))
    image.save(path, compress_level=1)
    return path


def test_frame_times_follow_a_30_fps_clock() -> None:
    times = svg_video.frame_times(17.8)
    assert len(times) == 534
    assert times[0] == 0
    assert all(abs(b - a - 1 / 30) < 1e-3 for a, b in pairwise(times))
    assert times[-1] == round(533 / 30, 4)


def test_batches_are_groups_of_eight_with_a_short_tail() -> None:
    times = svg_video.frame_times(17.8)
    groups = svg_video.batches(times)
    assert [len(group) for group in groups] == [8] * 66 + [6]
    assert [t for group in groups for t in group] == times


def test_batch_page_isolates_each_svg_copy_and_seeks_it() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>a &amp; "b" \'c\'</text></svg>'
    times = [0.0, 0.0333, 1.5]
    page = svg_video.batch_page(svg, times)
    assert "<svg" not in page
    frames = [attrs for tag, attrs in parse(page) if tag == "iframe"]
    assert [frame["data-t"] for frame in frames] == ["0.0", "0.0333", "1.5"]
    for frame in frames:
        assert frame["sandbox"] == "allow-same-origin"
        assert svg in frame["srcdoc"]
        metas = [attrs for tag, attrs in parse(frame["srcdoc"]) if tag == "meta"]
        csp = [m for m in metas if m.get("http-equiv") == "Content-Security-Policy"]
        assert [m["content"] for m in csp] == [svg_video.CSP]
    assert "pauseAnimations()" in page
    assert "setCurrentTime(Number(frame.dataset.t))" in page


def test_browser_command_pins_motion_scale_and_grid(tmp_path) -> None:
    png = tmp_path / "shot.png"
    command = svg_video.browser_command("chrome", tmp_path / "page.html", png, "profile")
    assert command[0] == "chrome"
    for flag in (
        "--headless=new",
        "--force-prefers-no-reduced-motion",
        "--force-device-scale-factor=1",
        "--window-size=4320,3840",
        f"--screenshot={png.resolve()}",
        "--user-data-dir=profile",
    ):
        assert flag in command
    assert command[-1] == (tmp_path / "page.html").resolve().as_uri()


def test_encode_command_targets_instagram_h264(tmp_path) -> None:
    output = tmp_path / "out.mp4"
    command = svg_video.encode_command(output)
    pairs = set(pairwise(command))
    assert command[0] == "ffmpeg"
    assert command[-1] == str(output)
    for pair in (
        ("-c:v", "libx264"),
        ("-profile:v", "high"),
        ("-pix_fmt", "yuv420p"),
        ("-r", "30"),
        ("-movflags", "+faststart"),
        ("-s", "1080x1920"),
        ("-i", "pipe:0"),
    ):
        assert pair in pairs
    assert "-an" in command


def test_tiles_crop_each_frame_in_grid_order(tmp_path) -> None:
    colors = [(index * 30, 80, 160) for index in range(6)]
    frames = svg_video.tiles(sheet(tmp_path / "grid.png", colors), len(colors))
    assert len(frames) == 6
    for frame, color in zip(frames, colors, strict=True):
        assert frame.size == (W, H)
        assert frame.getpixel((0, 0)) == color
        assert frame.getpixel((W - 1, H - 1)) == color
        assert frame.getpixel((15, 15)) == MARK


def test_tiles_refuse_a_blank_frame(tmp_path) -> None:
    png = sheet(tmp_path / "blank.png", [(11, 22, 33)] * 3, marked=False)
    with pytest.raises(SvgVideoError, match="blank"):
        svg_video.tiles(png, 3)


def test_tiles_refuse_a_wrong_size_sheet(tmp_path) -> None:
    png = tmp_path / "small.png"
    Image.new("RGB", (W, H), (1, 2, 3)).save(png)
    with pytest.raises(SvgVideoError, match="expected grid"):
        svg_video.tiles(png, 1)


@pytest.mark.parametrize("missing", ["browser", "ffmpeg", "ffprobe"])
def test_ensure_available_requires_every_tool(monkeypatch, missing) -> None:
    browser = None if missing == "browser" else "/usr/bin/chrome"
    monkeypatch.setattr(svg_video, "find_browser", lambda: browser)
    monkeypatch.setattr(
        svg_video.shutil, "which", lambda name: None if name == missing else f"/usr/bin/{name}"
    )
    with pytest.raises(SvgVideoError, match="Chrome" if missing == "browser" else missing):
        svg_video.ensure_available()


def test_ensure_available_returns_the_browser(monkeypatch) -> None:
    monkeypatch.setattr(svg_video, "find_browser", lambda: "/usr/bin/chrome")
    monkeypatch.setattr(svg_video.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert svg_video.ensure_available() == "/usr/bin/chrome"


class Stdin:
    def __init__(self) -> None:
        self.frames: list[tuple[int, bytes]] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.frames.append((len(data), data[:3]))

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def encoder(monkeypatch):
    """Fake shoot() sheets that encode the frame index, and a fake ffmpeg process."""
    state = {"code": 0, "procs": []}

    def shoot(browser, svg, times, stem):
        return sheet(stem.with_suffix(".png"), [(round(t * 30), 100, 50) for t in times])

    class Process:
        def __init__(self, command, *, stdin, stdout, stderr) -> None:
            self.command, self.stdin, self.killed = command, Stdin(), False
            stderr.write("encoder exploded" if state["code"] else "")
            state["procs"].append(self)

        def wait(self, timeout=None) -> int:
            return state["code"]

        def kill(self) -> None:
            self.killed = True

    monkeypatch.setattr(svg_video, "shoot", shoot)
    monkeypatch.setattr(svg_video.subprocess, "Popen", Process)
    return state


def test_render_streams_every_frame_in_order(encoder, tmp_path) -> None:
    output = tmp_path / "reel.mp4"
    assert svg_video.render("<svg/>", 0.4, output, browser="chrome") == output
    (process,) = encoder["procs"]
    assert process.command == svg_video.encode_command(output)
    assert process.stdin.closed
    assert [size for size, _ in process.stdin.frames] == [W * H * 3] * 12
    assert [head for _, head in process.stdin.frames] == [bytes((i, 100, 50)) for i in range(12)]


def test_render_raises_when_the_encoder_fails(encoder, tmp_path) -> None:
    encoder["code"] = 1
    with pytest.raises(SvgVideoError, match=r"rc=1.*encoder exploded"):
        svg_video.render("<svg/>", 0.4, tmp_path / "reel.mp4", browser="chrome")


def probe_result(*, audio: bool = True) -> dict:
    video = {"codec_type": "video", "codec_name": "h264", "profile": "High", "width": 1080}
    video |= {"height": 1920, "pix_fmt": "yuv420p", "avg_frame_rate": "30/1"}
    streams = [video]
    if audio:
        streams.append({"codec_type": "audio", "codec_name": "aac", "channels": 2})
    return {"format": {"duration": "12.300000", "size": "2500000"}, "streams": streams}


@pytest.mark.parametrize(("audio", "duration"), [(True, 12.3), (True, 12.1), (False, 12.5)])
def test_verify_accepts_a_reel_within_spec(monkeypatch, audio, duration) -> None:
    monkeypatch.setattr(reel_probe, "probe", lambda path: probe_result(audio=audio))
    summary = reel_probe.verify(Path("reel.mp4"), duration, audio=audio)
    assert summary["duration"] == pytest.approx(12.3)
    assert summary["bytes"] == 2_500_000
    assert (summary["audio"] is not None) is audio


def _video(**fields):
    return lambda info: info["streams"][0].update(fields)


@pytest.mark.parametrize(
    ("edit", "audio", "problem"),
    [
        (_video(codec_name="hevc"), True, "H.264 High"),
        (_video(profile="Main"), True, "H.264 High"),
        (_video(width=720, height=1280), True, "1080x1920"),
        (_video(pix_fmt="yuv444p"), True, "yuv420p"),
        (_video(avg_frame_rate="25/1"), True, "30 fps"),
        (lambda info: info["format"].update(duration="12.56"), True, "about 12.3 s"),
        (lambda info: info["streams"].pop(), True, "AAC audio"),
        (lambda info: None, False, "no audio stream"),
        (lambda info: info["format"].update(size="100000001"), True, "below 100 MB"),
    ],
    ids=["codec", "profile", "size", "pix_fmt", "fps", "duration", "no-audio", "audio", "bytes"],
)
def test_verify_rejects_each_wrong_field(monkeypatch, edit, audio, problem) -> None:
    info = probe_result()
    edit(info)
    monkeypatch.setattr(reel_probe, "probe", lambda path: info)
    with pytest.raises(SvgVideoError, match=problem):
        reel_probe.verify(Path("reel.mp4"), 12.3, audio=audio)


TOOLS_MISSING = (
    svg_video.find_browser() is None
    or shutil.which("ffmpeg") is None
    or shutil.which("ffprobe") is None
)


@pytest.mark.skipif(TOOLS_MISSING, reason="needs Chrome or Chromium, ffmpeg and ffprobe")
def test_real_render_of_the_stat_ring_sample_meets_the_reel_spec(tmp_path) -> None:
    scenes = json.loads(SAMPLES.read_text("utf-8"))["scenes"]
    item = copy.deepcopy(next(s for s in scenes if s["name"] == "stat-ring"))
    built = compose(item["scene"], source_line=item["source_line"])
    seconds = 2.0  # the hook and the start of the ring fill keep this test fast
    output = svg_video.render(built.svg, seconds, tmp_path / "ring.mp4")
    summary = reel_probe.verify(output, seconds, audio=False)
    assert summary["video"]["codec_name"] == "h264"
    assert summary["duration"] == pytest.approx(seconds, abs=0.25)
