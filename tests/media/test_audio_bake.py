from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.media import audio_bake


def test_bake_builds_correct_ffmpeg_command_for_5s(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = audio_bake.bake(video, track, duration_s=5)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "128k"
    assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "48000"
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

    with patch("src.media.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        audio_bake.bake(video, track, duration_s=9)

    cmd = mock_run.call_args[0][0]
    assert "afade=t=out:st=8.5:d=0.5" in " ".join(cmd)


def test_bake_raises_on_ffmpeg_failure(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid data")
        with pytest.raises(audio_bake.AudioBakeError):
            audio_bake.bake(video, track, duration_s=5)


def test_bake_raises_when_ffmpeg_not_installed(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with (
        patch("src.media.audio_bake.shutil.which", return_value=None),
        pytest.raises(audio_bake.AudioBakeError, match="ffmpeg not on PATH"),
    ):
        audio_bake.bake(video, track, duration_s=5)
