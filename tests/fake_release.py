"""An in-memory draft release `reel-queue` behind the GitHub calls `ReelQueue` makes, and an
ffprobe that reads the fake video bytes, so queue runs execute the real adapter and flow."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE = "https://api.github.com/repos/owner/repo"
GOOD = b"MP4|30/1|"
BAD_FPS = b"MP4|30.0001|"  # what three queued videos read on 2026-11-26


def video(spec: bytes = GOOD, duration: float = 60.0) -> bytes:
    """Fake MP4 bytes; ffprobe exits 1 when the `|END` marker is cut off."""
    return spec + str(duration).encode() + b"|" + b"x" * 64 + b"|END"


def entry(title: str, pillar: str = "history-timeline", **fields: Any) -> dict[str, Any]:
    return {
        "title": title,
        "pillar": pillar,
        "caption": f"{title} in one minute.",
        "hashtags": "#history",
        "duration_s": 60.0,
        "audio": True,
        **fields,
    }


class Response:
    def __init__(self, payload: Any = None, content: bytes = b"") -> None:
        self.payload, self.content = payload, content

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        return None


@dataclass
class Release:
    assets: dict[int, dict[str, Any]] = field(default_factory=dict)
    served: dict[int, bytes] = field(default_factory=dict)  # a download that differs
    renames: list[tuple[int, str]] = field(default_factory=list)
    probed: list[bytes] = field(default_factory=list)
    ffprobe: str = "works"  # or missing, timeout, killed, broken (exits 1 on everything)

    def add(self, name: str, body: bytes = b"", *, listed: bool = True) -> int:
        number = 100 + len(self.assets)
        self.assets[number] = {
            "id": number,
            "name": name,
            "created_at": f"2026-11-20T00:{len(self.assets):02d}:00Z",
            "body": body,
            "size": len(body) if listed else None,
            "digest": "sha256:" + hashlib.sha256(body).hexdigest() if listed else None,
        }
        return number

    def pair(
        self, slug: str, meta: dict[str, Any] | bytes, mp4: bytes | None = None
    ) -> tuple[int, int]:
        """Upload `<slug>.json` then `<slug>.mp4`; returns their ids (json, mp4)."""
        body = meta if isinstance(meta, bytes) else json.dumps(meta).encode()
        return self.add(f"{slug}.json", body), self.add(f"{slug}.mp4", mp4 or video())

    def names(self) -> list[str]:
        return sorted(asset["name"] for asset in self.assets.values())

    def name(self, number: int) -> str:
        return self.assets[number]["name"]

    def get(self, url: str, **kwargs: Any) -> Response:
        path = url.removeprefix(BASE)
        if path == "/releases":
            return Response([{"id": 7, "draft": True, "tag_name": "reel-queue"}])
        if path == "/releases/7/assets":
            # GitHub's listing: by name, 100 a page, without the bytes; an unlisted size is absent
            listing = [
                {key: value for key, value in asset.items() if key != "body" and value is not None}
                for asset in sorted(self.assets.values(), key=lambda asset: asset["name"])
            ]
            start = (kwargs["params"].get("page", 1) - 1) * 100
            return Response(listing[start : start + 100])
        number = int(path.rsplit("/", 1)[1])
        return Response(content=self.served.get(number, self.assets[number]["body"]))

    def patch(self, url: str, **kwargs: Any) -> Response:
        number = int(url.rsplit("/", 1)[1])
        self.assets[number]["name"] = kwargs["json"]["name"]
        self.renames.append((number, kwargs["json"]["name"]))
        return Response()

    def run(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        """ffprobe: the spec and duration come from the fake bytes."""
        if self.ffprobe == "missing":
            raise FileNotFoundError("ffprobe")
        if self.ffprobe == "timeout":
            raise subprocess.TimeoutExpired(command, 60)
        if self.ffprobe == "killed":
            raise subprocess.CalledProcessError(-9, command)
        if command[-1] == "-version":  # the health check before a file is called bad
            code = 1 if self.ffprobe == "broken" else 0
            return subprocess.CompletedProcess(command, code, stdout="", stderr="")
        if self.ffprobe == "broken":
            raise subprocess.CalledProcessError(1, command)
        body = Path(command[-1]).read_bytes()
        self.probed.append(body)
        if not body.endswith(b"|END"):
            raise subprocess.CalledProcessError(1, command)
        _, fps, duration, _rest = body.split(b"|", 3)
        stream = {"codec_type": "video", "codec_name": "h264", "profile": "High"}
        stream |= {"width": 1080, "height": 1920, "pix_fmt": "yuv420p"}
        stream |= {"avg_frame_rate": fps.decode()}
        sound = {"codec_type": "audio", "codec_name": "aac", "channels": 2}
        info = {"format": {"duration": duration.decode(), "size": str(len(body))}}
        info["streams"] = [stream, sound]
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(info), stderr="")
