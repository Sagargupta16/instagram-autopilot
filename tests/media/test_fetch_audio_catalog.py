"""The licensed audio catalog and its fetch script: hashes, failures and the manifest."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from scripts import fetch_audio_catalog as fetch
from src.media.audio_manifest import validate_track

TRACKED = Path(fetch.__file__).resolve().parents[1] / "assets" / "audio" / "catalog.json"
AUDIO = b"ID3 fake mp3 bytes"


class Response:
    def __init__(self, body: bytes, status: int = 200, kind: str = "audio/mpeg") -> None:
        self.body, self.status, self.headers = body, status, {"Content-Type": kind}

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


def catalog(tmp_path: Path, *tracks: dict) -> Path:
    data = json.loads(TRACKED.read_text("utf-8"))
    data["tracks"] = list(tracks)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data), "utf-8")
    return path


def track(track_id: str = "mixkit-tapis-615", theme: str = "cinematic", body: bytes = AUDIO):
    return {
        "track_id": track_id,
        "theme": theme,
        "title": "Tapis",
        "artist": "Eugenio Mininni",
        "page_url": "https://mixkit.co/free-stock-music/tag/cinematic/",
        "download_url": f"https://assets.mixkit.co/music/{track_id}.mp3",
        "duration_s": 163.2,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def opener_for(responses: dict[str, Response], calls: list[str]):
    def opener(request, timeout):
        calls.append(request.full_url)
        assert timeout == 60
        assert "InstagramAutopilot" in request.get_header("User-agent")
        return responses[request.full_url]

    return opener


def test_tracked_catalog_lists_licensed_mixkit_tracks_per_theme() -> None:
    data = json.loads(TRACKED.read_text("utf-8"))
    assert data["license"] == "Mixkit Stock Music Free License"
    assert data["license_url"] == "https://mixkit.co/license/#musicFree"
    terms = " ".join(data["terms"]).lower()
    assert "social media video posts" in terms
    assert "no attribution" in terms
    assert "rights-management service" in terms
    assert "never committed" in terms
    tracks = data["tracks"]
    assert 12 <= len(tracks) <= 18
    themes = Counter(item["theme"] for item in tracks)
    assert set(themes) == {"chill", "upbeat", "cinematic"}
    assert min(themes.values()) >= 4
    assert len({item["track_id"] for item in tracks}) == len(tracks)
    for item in tracks:
        assert re.fullmatch(r"https://assets\.mixkit\.co/music/\d+/\d+\.mp3", item["download_url"])
        assert item["page_url"].startswith("https://mixkit.co/free-stock-music/")
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert item["title"] and item["artist"]
        assert item["duration_s"] >= 60  # longer than any Reel
        assert item["bytes"] > 0


def test_fetch_verifies_hashes_and_writes_the_picker_manifest(tmp_path) -> None:
    item = track()
    calls: list[str] = []
    opener = opener_for({item["download_url"]: Response(AUDIO)}, calls)
    assert fetch.fetch(catalog(tmp_path, item), tmp_path, opener=opener) == []
    saved = tmp_path / "cinematic" / "mixkit-tapis-615.mp3"
    assert saved.read_bytes() == AUDIO
    manifest = json.loads((tmp_path / fetch.MANIFEST_NAME).read_text("utf-8"))
    (entry,) = manifest["tracks"]
    assert entry["filename"] == "cinematic/mixkit-tapis-615.mp3"
    assert entry["theme_tags"] == ["cinematic"]
    assert entry["attribution_required"] is False
    assert entry["license"] == "Mixkit Stock Music Free License"
    assert validate_track(entry, tmp_path).path == saved.resolve()
    assert not list(tmp_path.rglob("*.part"))


def test_a_file_with_the_right_hash_is_not_downloaded_again(tmp_path) -> None:
    item = track()
    (tmp_path / "cinematic").mkdir()
    (tmp_path / "cinematic" / "mixkit-tapis-615.mp3").write_bytes(AUDIO)
    calls: list[str] = []
    assert fetch.fetch(catalog(tmp_path, item), tmp_path, opener=opener_for({}, calls)) == []
    assert calls == []


@pytest.mark.parametrize(
    "response",
    [
        Response(b"tampered bytes"),
        Response(AUDIO, status=403),
        Response(AUDIO, kind="text/html"),
    ],
    ids=["hash-mismatch", "forbidden", "not-audio"],
)
def test_a_bad_download_is_skipped_and_never_kept(tmp_path, capsys, response) -> None:
    good, bad = track("mixkit-curiosity-480", "chill"), track()
    (tmp_path / "cinematic").mkdir()
    (tmp_path / "cinematic" / "mixkit-tapis-615.mp3").write_bytes(b"stale copy")
    responses = {good["download_url"]: Response(AUDIO), bad["download_url"]: response}
    failed = fetch.fetch(catalog(tmp_path, good, bad), tmp_path, opener=opener_for(responses, []))
    assert failed == ["mixkit-tapis-615"]
    assert not (tmp_path / "cinematic" / "mixkit-tapis-615.mp3").exists()
    manifest = json.loads((tmp_path / fetch.MANIFEST_NAME).read_text("utf-8"))
    assert [entry["track_id"] for entry in manifest["tracks"]] == ["mixkit-curiosity-480"]
    assert "skip mixkit-tapis-615" in capsys.readouterr().err


def test_network_errors_are_reported_per_track(tmp_path) -> None:
    def offline(request, timeout):
        raise OSError("network unreachable")

    assert fetch.fetch(catalog(tmp_path, track()), tmp_path, opener=offline) == ["mixkit-tapis-615"]
    assert json.loads((tmp_path / fetch.MANIFEST_NAME).read_text("utf-8")) == {"tracks": []}


def test_only_https_downloads_and_known_themes(tmp_path) -> None:
    plain = {**track(), "download_url": "http://assets.mixkit.co/music/615/615.mp3"}
    assert fetch.fetch(catalog(tmp_path, plain), tmp_path, opener=opener_for({}, [])) == [
        "mixkit-tapis-615"
    ]
    with pytest.raises(ValueError, match="unsupported theme"):
        fetch.fetch(catalog(tmp_path, track(theme="ambient")), tmp_path, opener=opener_for({}, []))


def test_main_exits_non_zero_when_a_track_is_missing(tmp_path, monkeypatch) -> None:
    path = catalog(tmp_path, track())
    monkeypatch.setattr("sys.argv", ["fetch_audio_catalog.py", "--catalog", str(path)])
    monkeypatch.setattr(fetch, "fetch", lambda *args, **kwargs: ["mixkit-tapis-615"])
    assert fetch.main() == 1
    monkeypatch.setattr(fetch, "fetch", lambda *args, **kwargs: [])
    assert fetch.main() == 0
