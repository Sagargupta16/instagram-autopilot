from __future__ import annotations

import json

import pytest

from scripts import curate_audio


def legacy(tmp_path, **overrides):
    (tmp_path / "ambient").mkdir(exist_ok=True)
    (tmp_path / "ambient" / "track.mp3").write_bytes(b"audio")
    row = {
        "theme": "ambient",
        "title": "Title",
        "artist": "Artist",
        "file": "ambient/track.mp3",
        "duration_s": 60,
        "license": "CC-BY 4.0",
        "attribution": "Music by Artist under CC BY 4.0",
        "source": "https://example.com/audio",
    }
    row.update(overrides)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps([row]))
    return path


def test_explicit_legacy_import_keeps_attribution_and_does_not_change_source(tmp_path) -> None:
    source = legacy(tmp_path)
    before = source.read_bytes()
    output = tmp_path / "audio_manifest.json"
    curate_audio.import_legacy(source, output, tmp_path)
    row = json.loads(output.read_text())["tracks"][0]
    assert row["theme_tags"] == ["ambient"]
    assert row["attribution_required"] is True
    assert row["attribution"] == "Music by Artist under CC BY 4.0"
    assert row["filename"] == "ambient/track.mp3"
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"file": "../outside.mp3"},
        {"file": "missing.mp3"},
        {"theme": "invalid"},
        {"attribution": ""},
        {"duration_s": -1},
        {"duration_s": float("nan")},
        {"license": ""},
        {"source": "javascript:invalid"},
    ],
)
def test_invalid_legacy_import_never_replaces_manifest(tmp_path, overrides) -> None:
    source = legacy(tmp_path, **overrides)
    destination = tmp_path / "audio_manifest.json"
    destination.write_text('{"tracks":[]}')
    with pytest.raises(ValueError):
        curate_audio.import_legacy(source, destination, tmp_path)
    assert destination.read_text() == '{"tracks":[]}'


@pytest.mark.parametrize("theme", ["chill", "upbeat", "cinematic", "ambient", "energetic"])
def test_curator_cli_accepts_all_content_themes(monkeypatch, theme) -> None:
    called = []
    monkeypatch.setattr("sys.argv", ["curate_audio.py", "--theme", theme, "--api-key", "test"])
    monkeypatch.setattr(curate_audio, "curate", lambda *args: called.append(args))
    curate_audio.main()
    assert called == [(theme, 10, "test")]
