from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.media.audio import audio_bake


def test_timeout_is_audio_bake_error(tmp_path: Path) -> None:
    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value="ffmpeg"),
        patch(
            "src.media.audio.audio_bake.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 120),
        ),
        pytest.raises(audio_bake.AudioBakeError, match="timed out"),
    ):
        audio_bake.bake(tmp_path / "in.mp4", tmp_path / "audio.mp3", 5)


def test_bake_builds_correct_ffmpeg_command_for_5s(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("src.media.audio.audio_bake.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = audio_bake.bake(video, track, duration_s=5)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    for flag, value in (("-c:v", "copy"), ("-c:a", "aac"), ("-b:a", "128k"), ("-ar", "48000")):
        assert flag in cmd
        assert cmd[cmd.index(flag) + 1] == value
    joined = " ".join(cmd)
    assert "afade=t=in:st=0:d=0.5" in joined
    assert "afade=t=out:st=4.5:d=0.5" in joined
    assert "+faststart" in joined
    assert result == tmp_path / "in-baked.mp4"


def test_bake_9s_uses_correct_fadeout_offset(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("src.media.audio.audio_bake.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        audio_bake.bake(video, track, duration_s=9)

    cmd = mock_run.call_args[0][0]
    assert "afade=t=out:st=8.5:d=0.5" in " ".join(cmd)


@pytest.mark.parametrize(
    ("seconds", "start"), [(17.8, "17.3"), (12.3, "11.8"), (20.25, "19.75"), (0.4, "0")]
)
def test_fade_out_ends_at_the_real_fractional_duration(tmp_path: Path, seconds, start) -> None:
    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("src.media.audio.audio_bake.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        audio_bake.bake(tmp_path / "in.mp4", tmp_path / "track.mp3", duration_s=seconds)
    joined = " ".join(mock_run.call_args[0][0])
    assert f"afade=t=out:st={start}:d=0.5" in joined
    assert "-shortest" in joined


def test_bake_raises_on_ffmpeg_failure(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("src.media.audio.audio_bake.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid data")
        with pytest.raises(audio_bake.AudioBakeError):
            audio_bake.bake(video, track, duration_s=5)


def test_bake_raises_when_ffmpeg_not_installed(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with (
        patch("src.media.audio.audio_bake.shutil.which", return_value=None),
        pytest.raises(audio_bake.AudioBakeError, match="ffmpeg not on PATH"),
    ):
        audio_bake.bake(video, track, duration_s=5)
