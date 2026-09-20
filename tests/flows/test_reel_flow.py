from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.flows import reel_flow as flow
from src.media import audio_picker


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        flow, "settings", SimpleNamespace(s3_video_bucket="s3://bucket/", allow_silent_reels=False)
    )
    track = SimpleNamespace(
        path=tmp_path / "audio.mp3", track_id="track", attribution="Music by Artist, CC BY 4.0"
    )
    track.path.write_bytes(b"audio")
    select = Mock(return_value=track)
    monkeypatch.setattr(audio_picker, "select", select, raising=False)
    record = Mock()
    monkeypatch.setattr(audio_picker, "record_usage", record, raising=False)
    generate = Mock(return_value="s3://bucket/output.mp4")
    monkeypatch.setattr(flow, "generate_video", generate)

    def download(uri, destination):
        destination.write_bytes(b"video")
        return destination

    monkeypatch.setattr(flow, "download_video", Mock(side_effect=download), raising=False)
    monkeypatch.setattr(flow.audio_bake, "bake", lambda video, track, duration: video)
    monkeypatch.setattr(flow.audio_bake, "ensure_available", Mock(), raising=False)
    upload = Mock(return_value="https://res.cloudinary.com/x/video/upload/a.mp4")
    monkeypatch.setattr(flow, "upload_video", upload)
    publish = Mock(return_value="reel-media")
    monkeypatch.setattr(flow, "publish_reel", publish)
    fallback = Mock(return_value="carousel-media")
    monkeypatch.setattr(flow, "post_carousel", fallback)
    monkeypatch.setattr(flow, "resolve_location_id", Mock(return_value=None))
    return SimpleNamespace(
        select=select,
        record=record,
        generate=generate,
        upload=upload,
        publish=publish,
        fallback=fallback,
        track=track,
    )


def post(**kwargs):
    return flow.post_reel(
        {"video_prompt": "waves", "audio_theme": "chill"},
        "caption",
        "image-model",
        "video-model",
        **kwargs,
    )


def test_missing_audio_falls_back_before_paid_generation(pipeline) -> None:
    pipeline.select.side_effect = audio_picker.NoTrackAvailableError("empty")
    callback = Mock()
    assert post(dry_run=False, before_publish=callback) == "carousel-media"
    pipeline.generate.assert_not_called()
    assert pipeline.fallback.call_args.kwargs["before_publish"] is callback


def test_dryrun_never_uploads_publishes_or_records_history(pipeline, tmp_path) -> None:
    assert post(dry_run=True) is None
    pipeline.upload.assert_not_called()
    pipeline.publish.assert_not_called()
    pipeline.record.assert_not_called()
    assert list((tmp_path / "output").rglob("*.mp4"))
    assert (
        pipeline.track.attribution in next((tmp_path / "output").rglob("caption.json")).read_text()
    )


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("ffmpeg", 120), OSError("disk")])
def test_prepublication_failures_fall_back(pipeline, monkeypatch, failure) -> None:
    monkeypatch.setattr(flow.audio_bake, "bake", Mock(side_effect=failure))
    assert post(dry_run=False) == "carousel-media"
    pipeline.publish.assert_not_called()


def test_upload_sdk_error_falls_back(pipeline) -> None:
    pipeline.upload.side_effect = RuntimeError("SDK upload error")
    assert post(dry_run=False) == "carousel-media"
    pipeline.record.assert_not_called()
    assert pipeline.fallback.call_args.args[1] == "caption"


def test_success_returns_receipt_callback_and_attribution(pipeline) -> None:
    callback = Mock()
    assert post(dry_run=False, before_publish=callback) == "reel-media"
    assert pipeline.publish.call_args.kwargs["before_publish"] is callback
    assert pipeline.track.attribution in pipeline.publish.call_args.kwargs["caption"]
    pipeline.record.assert_called_once_with(pipeline.track)


@pytest.mark.parametrize("error", [OSError("disk full"), ValueError("invalid history")])
def test_audio_history_failure_preserves_confirmed_publication(pipeline, caplog, error) -> None:
    pipeline.record.side_effect = error
    callback = Mock()

    def confirmed(**kwargs):
        kwargs["before_publish"]("container")
        return "reel-media"

    pipeline.publish.side_effect = confirmed
    assert post(dry_run=False, before_publish=callback) == "reel-media"
    callback.assert_called_once_with("container")
    pipeline.publish.assert_called_once()
    pipeline.record.assert_called_once_with(pipeline.track)
    pipeline.fallback.assert_not_called()
    assert "reel-media" in caplog.text
    assert "audio history" in caplog.text.lower()
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_no_fallback_after_ambiguous_publish(pipeline) -> None:
    callback = Mock()

    def ambiguous(**kwargs):
        kwargs["before_publish"]("container")
        raise TimeoutError("publication outcome unknown")

    pipeline.publish.side_effect = ambiguous
    with pytest.raises(TimeoutError, match="unknown"):
        post(dry_run=False, before_publish=callback)
    callback.assert_called_once_with("container")
    pipeline.fallback.assert_not_called()
    pipeline.record.assert_not_called()


def test_no_fallback_after_callback_failure(pipeline) -> None:
    pipeline.publish.side_effect = lambda **kwargs: kwargs["before_publish"]("container")
    with pytest.raises(OSError):
        post(dry_run=False, before_publish=Mock(side_effect=OSError("ledger failure")))
    pipeline.fallback.assert_not_called()


def test_silent_reel_requires_explicit_setting(pipeline, monkeypatch) -> None:
    pipeline.select.side_effect = audio_picker.NoTrackAvailableError("empty")
    monkeypatch.setattr(flow.settings, "allow_silent_reels", True)
    assert post(dry_run=False) == "reel-media"
    pipeline.fallback.assert_not_called()
    pipeline.record.assert_not_called()
