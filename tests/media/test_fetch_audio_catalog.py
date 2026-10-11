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


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Point the script's catalog, library and manifest at tmp_path; returns a writer."""
    monkeypatch.setattr(fetch, "CATALOG", tmp_path / "catalog.json")
    monkeypatch.setattr(fetch, "AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(fetch, "MANIFEST", tmp_path / "catalog_manifest.json")

    def write(*tracks: dict) -> Path:
        data = json.loads(TRACKED.read_text("utf-8"))
        data["tracks"] = list(tracks)
        fetch.CATALOG.write_text(json.dumps(data), "utf-8")
        return tmp_path

    return write


def manifest() -> dict:
    return json.loads(fetch.MANIFEST.read_text("utf-8"))


def track(track_id: str = "mixkit-tapis-615", theme: str = "cinematic", number: int = 615):
    return {
        "track_id": track_id,
        "theme": theme,
        "title": "Tapis",
        "artist": "Eugenio Mininni",
        "page_url": "https://mixkit.co/free-stock-music/tag/cinematic/",
        "download_url": f"https://assets.mixkit.co/music/{number}/{number}.mp3",
        "duration_s": 163.2,
        "bytes": len(AUDIO),
        "sha256": hashlib.sha256(AUDIO).hexdigest(),
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
        number = fetch.asset_number(item["download_url"])
        assert item["download_url"] == f"{fetch.MIXKIT_MUSIC}{number}/{number}.mp3"
        assert item["track_id"].endswith(f"-{number}")
        assert item["page_url"].startswith("https://mixkit.co/free-stock-music/")
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert item["title"]
        assert item["artist"]
        assert item["duration_s"] >= 60  # longer than any Reel
        assert item["bytes"] > 0


def test_fetch_verifies_hashes_and_writes_the_picker_manifest(library) -> None:
    item = track()
    root = library(item)
    calls: list[str] = []
    opener = opener_for({item["download_url"]: Response(AUDIO)}, calls)
    assert fetch.fetch(opener=opener) == []
    assert calls == ["https://assets.mixkit.co/music/615/615.mp3"]
    saved = root / "cinematic" / "mixkit-615.mp3"
    assert saved.read_bytes() == AUDIO
    (entry,) = manifest()["tracks"]
    assert entry == {
        "track_id": "mixkit-615",
        "filename": "cinematic/mixkit-615.mp3",
        "theme_tags": ["cinematic"],
        "license": "Mixkit Stock Music Free License",
        "license_url": "https://mixkit.co/license/#musicFree",
        "attribution_required": False,
        "attribution": "",
    }
    assert validate_track(entry, root).path == saved.resolve()
    assert not list(root.rglob("*.part"))


def test_a_file_with_the_right_hash_is_not_downloaded_again(library) -> None:
    root = library(track())
    (root / "cinematic").mkdir()
    (root / "cinematic" / "mixkit-615.mp3").write_bytes(AUDIO)
    calls: list[str] = []
    assert fetch.fetch(opener=opener_for({}, calls)) == []
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
def test_a_bad_download_is_skipped_and_never_kept(library, capsys, response) -> None:
    good, bad = track("mixkit-curiosity-480", "chill", 480), track()
    root = library(good, bad)
    (root / "cinematic").mkdir()
    (root / "cinematic" / "mixkit-615.mp3").write_bytes(b"stale copy")
    responses = {good["download_url"]: Response(AUDIO), bad["download_url"]: response}
    assert fetch.fetch(opener=opener_for(responses, [])) == ["mixkit-tapis-615"]
    assert not (root / "cinematic" / "mixkit-615.mp3").exists()
    assert [entry["track_id"] for entry in manifest()["tracks"]] == ["mixkit-480"]
    assert "skip mixkit-tapis-615" in capsys.readouterr().err


def test_network_errors_are_reported_per_track(library) -> None:
    def offline(request, timeout):
        raise OSError("network unreachable")

    library(track())
    assert fetch.fetch(opener=offline) == ["mixkit-tapis-615"]
    assert manifest() == {"tracks": []}


@pytest.mark.parametrize(
    "url",
    [
        "http://assets.mixkit.co/music/615/615.mp3",
        "https://example.com/music/615/615.mp3",
        "https://user@assets.mixkit.co/music/615/615.mp3",
        "https://assets.mixkit.co/music/615/616.mp3",
        "https://assets.mixkit.co/music/615/615.mp3?redirect=https://example.com",
        "file:///etc/passwd",
        None,
    ],
)
def test_downloads_only_come_from_a_mixkit_music_asset_url(library, url) -> None:
    library({**track(), "download_url": url})
    calls: list[str] = []
    assert fetch.fetch(opener=opener_for({}, calls)) == ["mixkit-tapis-615"]
    assert calls == []


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"theme": "ambient"}, "unsupported theme"),
        ({"track_id": "../../escape"}, "lowercase words and hyphens"),
        ({"track_id": "Mixkit Tapis"}, "lowercase words and hyphens"),
        ({"sha256": "abc"}, "64 lowercase hex digits"),
        ({"sha256": "A" * 64}, "64 lowercase hex digits"),
    ],
)
def test_a_malformed_catalog_entry_stops_the_fetch(library, overrides, problem) -> None:
    root = library({**track(), **overrides})
    opener = opener_for({}, [])
    with pytest.raises(ValueError, match=problem):
        fetch.fetch(opener=opener)
    assert not list(root.rglob("*.mp3"))


def test_a_catalog_under_another_license_is_refused(library) -> None:
    root = library(track())
    data = json.loads(fetch.CATALOG.read_text("utf-8"))
    data["license"] = "CC BY 4.0"
    fetch.CATALOG.write_text(json.dumps(data), "utf-8")
    with pytest.raises(ValueError, match="catalog license must be"):
        fetch.fetch(opener=opener_for({}, []))
    assert not list(root.rglob("*.mp3"))


def test_the_script_reads_only_the_tracked_catalog() -> None:
    library = TRACKED.parent
    assert fetch.CATALOG == TRACKED
    assert library == fetch.AUDIO_ROOT
    assert library / "catalog_manifest.json" == fetch.MANIFEST


def test_main_exits_non_zero_when_a_track_is_missing(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["fetch_audio_catalog.py"])
    monkeypatch.setattr(fetch, "fetch", lambda **kwargs: ["mixkit-tapis-615"])
    assert fetch.main() == 1
    monkeypatch.setattr(fetch, "fetch", lambda **kwargs: [])
    assert fetch.main() == 0
