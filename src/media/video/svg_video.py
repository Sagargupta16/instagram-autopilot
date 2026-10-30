"""Render an animated SVG to an Instagram-ready MP4 with headless Chrome and ffmpeg.

Each batch page tiles copies of the SVG in sandboxed srcdoc iframes at exactly 1080x1920
CSS px, pauses each copy's SMIL clock and seeks it to its own frame time, then one headless
screenshot captures the grid. Pillow crops the tiles and ffmpeg encodes H.264 (High,
yuv420p, BT.709, 30 fps, +faststart). ffprobe checks the delivered file before any upload.
"""

from __future__ import annotations

import html
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

WIDTH, HEIGHT, FPS = 1080, 1920, 30
COLS, ROWS = 4, 2
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
INSTALLS = (
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/opt/google/chrome/chrome",
    *(
        str(Path(os.environ[var], *parts))
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        if os.environ.get(var)
        for parts in (("Google", "Chrome", "Application", "chrome.exe"),)
    ),
)
CSP = "default-src 'none'; style-src 'unsafe-inline'"
SEEK = """<script>
function seek(frame) {
  const doc = frame.contentDocument, svg = doc && doc.querySelector("svg");
  if (svg && svg.pauseAnimations) { svg.pauseAnimations(); svg.setCurrentTime(Number(frame.dataset.t)); }
}
addEventListener("load", () => {
  const frames = [...document.querySelectorAll("iframe[data-t]")];
  frames.forEach(seek);
  requestAnimationFrame(() => { frames.forEach(seek); document.body.dataset.seeked = "1"; });
});
</script>"""


class SvgVideoError(Exception):
    """Rendering or encoding failed before anything was uploaded."""


def find_browser() -> str | None:
    for name in BROWSERS:
        if found := shutil.which(name):
            return found
    return next((path for path in INSTALLS if Path(path).is_file()), None)


def ensure_available() -> str:
    """Return the browser; fail before rendering when a tool is missing."""
    browser = find_browser()
    if browser is None:
        raise SvgVideoError("No Chrome or Chromium found for SVG rendering")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SvgVideoError(f"{tool} not on PATH -- install with apt-get install -y ffmpeg")
    return browser


def frame_times(duration: float, fps: int = FPS) -> list[float]:
    return [round(index / fps, 4) for index in range(round(duration * fps))]


def batches(times: list[float], size: int = COLS * ROWS) -> list[list[float]]:
    return [times[start : start + size] for start in range(0, len(times), size)]


def batch_page(svg: str, times: list[float], cols: int = COLS) -> str:
    inner = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        "<style>html,body{margin:0;overflow:hidden}svg{display:block}</style>"
        f"</head><body>{svg}</body></html>"
    )
    doc = html.escape(inner, quote=True)
    frames = "".join(
        f'<iframe sandbox="allow-same-origin" data-t="{t}" srcdoc="{doc}"></iframe>' for t in times
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "html,body{margin:0;overflow:hidden;background:#000}"
        f".grid{{display:grid;grid-template-columns:repeat({cols},{WIDTH}px);"
        f"grid-auto-rows:{HEIGHT}px}}"
        f"iframe{{display:block;border:0;width:{WIDTH}px;height:{HEIGHT}px}}"
        f'</style></head><body><div class="grid">{frames}</div>{SEEK}</body></html>'
    )


def browser_command(browser: str, page: Path, png: Path, profile: str) -> list[str]:
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--force-prefers-no-reduced-motion",
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile}",
        "--virtual-time-budget=3000",
        f"--window-size={COLS * WIDTH},{ROWS * HEIGHT}",
        f"--screenshot={png.resolve()}",
        page.resolve().as_uri(),
    ]
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        command.insert(1, "--no-sandbox")  # Chromium refuses to run as root otherwise
    return command


def shoot(browser: str, svg: str, times: list[float], stem: Path) -> Path:
    page, png = stem.with_suffix(".html"), stem.with_suffix(".png")
    page.write_text(batch_page(svg, times), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="svg-reel-profile-", ignore_cleanup_errors=True) as tmp:
        command = browser_command(browser, page, png, tmp)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SvgVideoError(f"browser failed: {type(error).__name__}") from error
    if not png.is_file() or png.stat().st_size == 0:
        detail = (result.stderr or result.stdout).strip()[-300:]
        raise SvgVideoError(f"browser wrote no screenshot (exit {result.returncode}): {detail}")
    return png


def tiles(png: Path, count: int, cols: int = COLS) -> list[Image.Image]:
    """Crop the grid into frames and refuse a blank one (a failed render is one flat color)."""
    with Image.open(png) as sheet:
        if sheet.size != (cols * WIDTH, ROWS * HEIGHT):
            raise SvgVideoError(f"screenshot is {sheet.size}, not the expected grid")
        frames = []
        for index in range(count):
            x, y = (index % cols) * WIDTH, (index // cols) * HEIGHT
            frame = sheet.crop((x, y, x + WIDTH, y + HEIGHT)).convert("RGB")
            if all(low == high for low, high in frame.getextrema()):
                raise SvgVideoError("a rendered frame is blank")
            frames.append(frame)
    return frames


X264 = [
    *("-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"),
    *("-c:v", "libx264", "-preset", "medium", "-tune", "animation", "-crf", "18"),
    *("-profile:v", "high", "-pix_fmt", "yuv420p", "-colorspace", "bt709"),
    *("-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", "-an"),
]


def encode_command(output: Path, fps: int = FPS) -> list[str]:
    """Raw RGB frames on stdin to H.264 High, yuv420p, BT.709, constant frame rate."""
    source = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}"]
    source += ["-framerate", str(fps), "-i", "pipe:0"]
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *source,
        *X264,
        "-r",
        str(fps),
        str(output),
    ]


def render(svg: str, duration: float, output: Path, *, browser: str | None = None) -> Path:
    """Write output as an MP4 of the SVG's first `duration` seconds."""
    browser = browser or ensure_available()
    groups = batches(frame_times(duration))
    workers = max(1, min(4, (os.cpu_count() or 2) // 2))
    log.info(
        "Rendering %d frames in %d batches on %d workers",
        sum(map(len, groups)),
        len(groups),
        workers,
    )
    with (
        tempfile.TemporaryDirectory(prefix="svg-reel-") as tmp,
        ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        shots = [
            pool.submit(shoot, browser, svg, group, Path(tmp) / f"batch{index:04d}")
            for index, group in enumerate(groups)
        ]
        errors = Path(tmp) / "ffmpeg.log"
        with errors.open("w+", encoding="utf-8") as log_file:
            encoder = subprocess.Popen(
                encode_command(output),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=log_file,
            )
            try:
                for shot, group in zip(shots, groups, strict=True):
                    png = shot.result()
                    for frame in tiles(png, len(group)):
                        encoder.stdin.write(frame.tobytes())
                    png.unlink()
                encoder.stdin.close()
                code = encoder.wait(timeout=300)
            except BaseException:
                encoder.kill()
                encoder.wait()
                for shot in shots:
                    shot.cancel()
                raise
            log_file.seek(0)
            detail = log_file.read()[-500:]
    if code != 0:
        raise SvgVideoError(f"ffmpeg failed (rc={code}): {detail}")
    return output
