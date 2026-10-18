"""Download the Kokoro narration model and voice pack, keeping a file only when its hash matches.

Usage:
    uv run --frozen python scripts/fetch_voice_model.py

Both files come from the kokoro-onnx model release (MIT code; the Kokoro-82M weights and voices
are Apache-2.0) and are saved under assets/voice/, which is gitignored: this public repository
never commits model weights. A file already on disk with the right sha256 is kept. A failed
download or a hash mismatch deletes the partial file and exits 1; SVG Reels then go out
music-only, as before narration existed. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = ROOT / "assets" / "voice"
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
FILES = {
    "kokoro-v1.0.fp16.onnx": "f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}
UA = "InstagramAutopilot/0.10 (+https://github.com/Sagargupta16/instagram-autopilot)"
CHUNK = 1 << 16


class FetchError(Exception):
    """A model file could not be downloaded or did not match its recorded hash."""


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()


def download(name: str, target: Path, sha256: str, *, opener=urllib.request.urlopen) -> None:
    """Write release file `name` to `target` only when its bytes hash to `sha256`."""
    url = RELEASE + name
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix=".part")
    try:
        sha = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as stream, opener(request, timeout=120) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise FetchError(f"{url} returned {status}")
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


def fetch(*, opener=urllib.request.urlopen) -> list[str]:
    """Download what is missing or stale; returns the names that failed."""
    failed = []
    for name, sha256 in FILES.items():
        target = VOICE_DIR / name
        try:
            if not (target.is_file() and digest(target) == sha256):
                download(name, target, sha256, opener=opener)
        except FetchError as error:
            target.unlink(missing_ok=True)
            failed.append(name)
            sys.stderr.write(f"skip {name}: {error}\n")
    sys.stdout.write(
        f"{len(FILES) - len(failed)} of {len(FILES)} voice files ready in {VOICE_DIR}\n"
    )
    return failed


def main() -> int:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args()
    return 1 if fetch() else 0


if __name__ == "__main__":
    raise SystemExit(main())
