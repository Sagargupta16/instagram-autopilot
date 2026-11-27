"""Which ffprobe failures are the video's own fault (SpecMismatch) and which are not."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.media.video import reel_probe
from src.media.video.svg_video import SvgVideoError

COMMAND = ["ffprobe"]


def runs(outcome, version=0):
    """ffprobe: `outcome` for a file, exit code `version` for the health check."""

    def run(command, **kwargs):
        if command[-1] == "-version":
            if isinstance(version, BaseException):
                raise version
            return subprocess.CompletedProcess(command, version, stdout="", stderr="")
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(command, 0, stdout=outcome, stderr="")

    return run


def test_ffprobe_rejecting_the_bytes_is_a_spec_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        reel_probe.subprocess, "run", runs(subprocess.CalledProcessError(1, COMMAND))
    )

    with pytest.raises(reel_probe.SpecMismatch):
        reel_probe.probe(Path("reel.mp4"))


@pytest.mark.parametrize(
    "version",
    [1, FileNotFoundError("ffprobe"), subprocess.TimeoutExpired(COMMAND, 30)],
    ids=["exits-1", "missing", "timeout"],
)
def test_an_ffprobe_that_does_not_run_at_all_is_not_a_spec_mismatch(monkeypatch, version) -> None:
    broken = runs(subprocess.CalledProcessError(1, COMMAND), version=version)
    monkeypatch.setattr(reel_probe.subprocess, "run", broken)

    with pytest.raises(SvgVideoError) as error:
        reel_probe.probe(Path("reel.mp4"))

    assert not isinstance(error.value, reel_probe.SpecMismatch)


@pytest.mark.parametrize(
    "outcome",
    [
        FileNotFoundError("ffprobe"),
        subprocess.TimeoutExpired(COMMAND, 60),
        subprocess.CalledProcessError(-9, COMMAND),
        "not json",
    ],
    ids=["missing", "timeout", "killed", "unparseable"],
)
def test_a_fault_of_ffprobe_itself_is_not_a_spec_mismatch(monkeypatch, outcome) -> None:
    monkeypatch.setattr(reel_probe.subprocess, "run", runs(outcome))

    with pytest.raises(SvgVideoError) as error:
        reel_probe.probe(Path("reel.mp4"))

    assert not isinstance(error.value, reel_probe.SpecMismatch)


def test_a_wrong_frame_rate_is_a_spec_mismatch(monkeypatch) -> None:
    video = {"codec_type": "video", "codec_name": "h264", "profile": "High", "width": 1080}
    video |= {"height": 1920, "pix_fmt": "yuv420p", "avg_frame_rate": "30.0001"}
    info = {"format": {"duration": "60.0", "size": "2500000"}, "streams": [video]}
    monkeypatch.setattr(reel_probe, "probe", lambda path: info)

    with pytest.raises(reel_probe.SpecMismatch, match="30 fps"):
        reel_probe.verify(Path("reel.mp4"), 60.0, audio=False)
