"""SVG Reel flow: every failure before the publisher skips the post; the boundary is unchanged."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.flows import reel_flow
from src.flows import svg_reel_flow as flow
from src.media import audio_bake, audio_picker, svg_video
from src.media.reel_svg import LayoutError, compose

SAMPLES = Path(__file__).resolve().parents[2] / "scripts" / "samples" / "svg_reel_scenes.json"
SCENES = {item["name"]: item["scene"] for item in json.loads(SAMPLES.read_text("utf-8"))["scenes"]}
SOURCE = {
    "title": "Sample coverage report",
    "source": "guardian",
    "category": "technology",
    "url": "https://www.theguardian.com/sample",
}
CREDIT = "Source: The Guardian https://www.theguardian.com/sample"
ATTRIBUTION = "Music by Artist, CC BY 4.0"
HANDLE = "@sample.account"


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reel_flow, "settings", SimpleNamespace(allow_silent_reels=False))
    track = SimpleNamespace(path=tmp_path / "audio.mp3", track_id="track", attribution=ATTRIBUTION)
    track.path.write_bytes(b"audio")
    select = Mock(return_value=track)
    monkeypatch.setattr(audio_picker, "select", select)
    record = Mock()
    monkeypatch.setattr(audio_picker, "record_usage", record)
    monkeypatch.setattr(audio_bake, "ensure_available", Mock())
    available = Mock(return_value="chrome")
    monkeypatch.setattr(svg_video, "ensure_available", available)

    def render(svg, duration, output):
        output.write_bytes(b"silent-mp4")
        return output

    def bake(video, track_path, seconds):
        baked = video.with_name("baked.mp4")
        baked.write_bytes(b"baked-mp4")
        return baked

    render_mock = Mock(side_effect=render)
    monkeypatch.setattr(svg_video, "render", render_mock)
    bake_mock = Mock(side_effect=bake)
    monkeypatch.setattr(audio_bake, "bake", bake_mock)
    verify = Mock(return_value={"duration": 12.3, "bytes": 9})
    monkeypatch.setattr(flow.reel_probe, "verify", verify)
    upload = Mock(return_value="https://res.cloudinary.com/x/video/upload/a.mp4")
    monkeypatch.setattr(flow, "upload_video", upload)
    publish = Mock(return_value="reel-media")
    monkeypatch.setattr(flow, "publish_reel", publish)
    monkeypatch.setattr(flow, "account_handle", Mock(return_value=HANDLE))
    return SimpleNamespace(
        select=select,
        record=record,
        available=available,
        render=render_mock,
        bake=bake_mock,
        verify=verify,
        upload=upload,
        publish=publish,
        track=track,
    )


def data(name: str = "stat-ring", look: int | None = None) -> dict:
    caption_data = {"scene": copy.deepcopy(SCENES[name]), "sources": [SOURCE]}
    caption_data["audio_theme"] = "chill"
    if look is not None:
        caption_data["look"] = look
    return caption_data


def post(caption_data=None, caption="caption", **kwargs):
    return flow.post_svg_reel(caption_data or data(), caption, **kwargs)


def assert_nothing_posted(pipeline) -> None:
    pipeline.upload.assert_not_called()
    pipeline.publish.assert_not_called()
    pipeline.record.assert_not_called()


def test_module_has_no_photo_fallback() -> None:
    assert not hasattr(flow, "post_carousel")


@pytest.mark.parametrize(
    "failure",
    [
        ("select", audio_picker.NoTrackAvailableError("empty")),
        ("ffmpeg", audio_bake.AudioBakeError("ffmpeg not on PATH")),
    ],
)
def test_missing_audio_skips_before_rendering(pipeline, monkeypatch, failure) -> None:
    where, error = failure
    if where == "select":
        pipeline.select.side_effect = error
    else:
        monkeypatch.setattr(audio_bake, "ensure_available", Mock(side_effect=error))
    callback = Mock()
    with pytest.raises(flow.SvgReelError) as raised:
        post(dry_run=False, before_publish=callback)
    assert raised.value.__cause__ is error
    pipeline.available.assert_not_called()
    pipeline.render.assert_not_called()
    callback.assert_not_called()
    assert_nothing_posted(pipeline)


def test_silent_reel_requires_the_explicit_setting(pipeline, monkeypatch) -> None:
    pipeline.select.side_effect = audio_picker.NoTrackAvailableError("empty")
    monkeypatch.setattr(reel_flow.settings, "allow_silent_reels", True)
    assert post(dry_run=False) == "reel-media"
    pipeline.bake.assert_not_called()
    assert pipeline.verify.call_args.kwargs["audio"] is False
    assert ATTRIBUTION not in pipeline.publish.call_args.kwargs["caption"]
    pipeline.record.assert_not_called()


@pytest.mark.parametrize("scene", [None, "steps"])
def test_missing_scene_skips(pipeline, scene) -> None:
    caption_data = {"sources": [SOURCE]} if scene is None else {"scene": scene}
    with pytest.raises(flow.SvgReelError, match="scene is missing"):
        post(caption_data, dry_run=False)
    pipeline.render.assert_not_called()
    assert_nothing_posted(pipeline)


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("render", svg_video.SvgVideoError("ffmpeg failed (rc=1)")),
        ("verify", svg_video.SvgVideoError("does not match the Reel spec")),
        ("compose", LayoutError("the ring does not fit")),
        ("render", OSError("disk full")),
    ],
)
def test_render_or_encode_failure_skips(pipeline, monkeypatch, target, error) -> None:
    owner = {"render": svg_video, "verify": flow.reel_probe, "compose": flow}[target]
    monkeypatch.setattr(owner, target, Mock(side_effect=error))
    callback = Mock()
    with pytest.raises(flow.SvgReelError) as raised:
        post(dry_run=False, before_publish=callback)
    assert raised.value.__cause__ is error
    known = isinstance(error, flow.KNOWN)
    assert (str(error) in str(raised.value)) is known
    assert type(error).__name__ in str(raised.value)
    callback.assert_not_called()
    assert_nothing_posted(pipeline)


def test_upload_failure_skips_without_leaking_the_sdk_message(pipeline) -> None:
    pipeline.upload.side_effect = RuntimeError("upload failed for api_secret=abc123")
    with pytest.raises(flow.SvgReelError, match="RuntimeError") as raised:
        post(dry_run=False)
    assert "abc123" not in str(raised.value)
    pipeline.publish.assert_not_called()
    pipeline.record.assert_not_called()


def test_dry_run_saves_the_evidence_and_never_posts(pipeline, tmp_path) -> None:
    caption_data = data()
    assert post(caption_data, dry_run=True) is None
    assert_nothing_posted(pipeline)
    (folder,) = (tmp_path / "output" / "dry-run").iterdir()
    assert (folder / "01.mp4").read_bytes() == b"baked-mp4"
    expected = compose(caption_data["scene"], source_line="Source: The Guardian", handle=HANDLE)
    assert (folder / "reel.svg").read_text("utf-8") == expected.svg
    evidence = json.loads((folder / "scene.json").read_text("utf-8"))
    assert evidence == {
        "scene": caption_data["scene"],
        "sources": [SOURCE],
        "look": 0,
        "thumb_offset_ms": expected.thumb_offset_ms,
    }
    caption = json.loads((folder / "caption.json").read_text("utf-8"))["caption"]
    assert caption == f"caption\n\n{CREDIT}\n\n{ATTRIBUTION}"


def test_success_passes_the_callback_and_credits_source_and_music(pipeline) -> None:
    callback = Mock()
    assert post(dry_run=False, before_publish=callback, audio_theme="upbeat") == "reel-media"
    pipeline.select.assert_called_once_with("upbeat")
    kwargs = pipeline.publish.call_args.kwargs
    assert kwargs["before_publish"] is callback
    assert kwargs["video_url"] == pipeline.upload.return_value
    assert kwargs["caption"] == f"caption\n\n{CREDIT}\n\n{ATTRIBUTION}"
    pipeline.upload.assert_called_once_with(b"baked-mp4")
    svg, duration, _ = pipeline.render.call_args.args
    assert svg.startswith("<svg")
    assert duration == pytest.approx(12.3)
    assert pipeline.bake.call_args.args[1:] == (pipeline.track.path, duration)  # not int(12.3)
    assert pipeline.verify.call_args.kwargs["audio"] is True
    pipeline.record.assert_called_once_with(pipeline.track)


def test_the_cover_frame_and_look_come_from_the_composer(pipeline) -> None:
    caption_data = data("steps-cicd", look=2)
    assert post(caption_data, dry_run=False) == "reel-media"
    reel = compose(caption_data["scene"], look=2, handle=HANDLE)
    svg = pipeline.render.call_args.args[0]
    assert svg == reel.svg
    assert "#fe8019" in svg  # the amber look's accent
    offset = pipeline.publish.call_args.kwargs["thumb_offset"]
    assert offset == reel.thumb_offset_ms == round(reel.cover * 1000)
    assert 0 < offset < (reel.duration - 2) * 1000  # the complete scene, before the end card


@pytest.mark.parametrize("error", [OSError("disk full"), ValueError("invalid history")])
def test_audio_history_failure_keeps_the_media_id(pipeline, caplog, error) -> None:
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
    assert "reel-media" in caplog.text
    assert "audio history" in caplog.text.lower()
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_ambiguous_publish_error_propagates_unwrapped(pipeline) -> None:
    callback = Mock()

    def ambiguous(**kwargs):
        kwargs["before_publish"]("container")
        raise TimeoutError("publication outcome unknown")

    pipeline.publish.side_effect = ambiguous
    with pytest.raises(TimeoutError, match="unknown"):
        post(dry_run=False, before_publish=callback)
    callback.assert_called_once_with("container")
    pipeline.publish.assert_called_once()
    pipeline.record.assert_not_called()


def test_callback_failure_propagates_unwrapped(pipeline) -> None:
    pipeline.publish.side_effect = lambda **kwargs: kwargs["before_publish"]("container")
    with pytest.raises(OSError, match="ledger failure"):
        post(dry_run=False, before_publish=Mock(side_effect=OSError("ledger failure")))
    pipeline.publish.assert_called_once()
    pipeline.record.assert_not_called()


def test_credited_appends_the_source_once_for_stat_scenes() -> None:
    once = flow.credited("caption", SCENES["stat-ring"], [SOURCE])
    assert once == f"caption\n\n{CREDIT}"
    assert flow.credited(once, SCENES["stat-ring"], [SOURCE]) == once
    named = {**SOURCE, "publisher": "Sample data"}
    assert flow.credited("c", SCENES["stat-bars"], [named]).endswith(
        "Source: Sample data " + named["url"]
    )


def test_credited_names_only_the_publisher_for_google_news_redirects() -> None:
    # A 2026-10-11 dry run put a 250-character news.google.com/rss/articles/... link here.
    redirect = {
        **SOURCE,
        "publisher": "Chron",
        "url": "https://news.google.com/rss/articles/CBMi?oc=5",
    }
    assert flow.credited("caption", SCENES["stat-ring"], [redirect]) == "caption\n\nSource: Chron"


@pytest.mark.parametrize("name", ["steps-cicd", "timeline-hubble"])
def test_credited_leaves_other_scenes_alone(name) -> None:
    assert flow.credited("caption", SCENES[name], [SOURCE]) == "caption"


@pytest.mark.parametrize(("length", "fits"), [(2172, True), (2173, False)])
def test_caption_limit_counts_the_attribution(pipeline, length, fits) -> None:
    caption = "x" * length  # plus "\n\n" and the 26-character music credit
    if fits:
        assert post(data("steps-cicd"), caption, dry_run=False) == "reel-media"
        assert len(pipeline.publish.call_args.kwargs["caption"]) == 2200
        return
    with pytest.raises(flow.SvgReelError, match="caption limit"):
        post(data("steps-cicd"), caption, dry_run=False)
    pipeline.render.assert_not_called()
    assert_nothing_posted(pipeline)


def test_source_credit_also_counts_toward_the_caption_limit(pipeline) -> None:
    caption = "x" * (2200 - len(f"\n\n{ATTRIBUTION}"))
    with pytest.raises(flow.SvgReelError, match="caption limit"):
        post(data("stat-ring"), caption, dry_run=False)
    pipeline.render.assert_not_called()
