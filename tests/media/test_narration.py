"""A narrated Reel that would run past 30 seconds is read again faster, within limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.media import narration
from src.media.narration import MAX_S, MAX_SPEED, Narration


def voice(seconds: float, speed: float = 1.0) -> Narration:
    return Narration(("hook", "body"), (Path("a.wav"), Path("b.wav")), (seconds, seconds), speed)


def test_quicker_takes_the_overrun_off_the_spoken_lines() -> None:
    assert narration.quicker(voice(10.0), 2.0) == pytest.approx(1.11)
    assert narration.quicker(voice(10.0), 15.0) == MAX_SPEED  # cannot save more than it says
    assert narration.quicker(voice(10.0), 8.0) == MAX_SPEED


@pytest.fixture
def reads(monkeypatch) -> list[float]:
    speeds: list[float] = []

    def fake(scene, workdir, *, voice: str, speed: float = 1.0) -> Narration:
        speeds.append(speed)
        return Narration(("hook",), (Path("a.wav"),), (24.0 / speed,), speed)

    monkeypatch.setattr(narration, "for_scene", fake)
    return speeds


def test_a_reel_within_the_limit_is_read_once(reads) -> None:
    result = narration.fitted({}, Path(), lambda pace: MAX_S - 1)
    assert reads == [1.0]
    assert result.speed == 1.0


def test_a_long_reel_is_read_again_faster(reads) -> None:
    result = narration.fitted({}, Path(), lambda pace: sum(pace) + 10.0)
    assert reads[0] == 1.0
    assert 1.0 < reads[1] <= MAX_SPEED
    assert result.speed == reads[1]


def test_a_failed_faster_read_keeps_the_first(monkeypatch) -> None:
    first = voice(14.0)
    answers = iter([first, None])
    monkeypatch.setattr(narration, "for_scene", lambda *args, **kwargs: next(answers))
    assert narration.fitted({}, Path(), lambda pace: MAX_S + 5) is first


def test_no_voice_means_no_narration(monkeypatch) -> None:
    monkeypatch.setattr(narration, "for_scene", lambda *args, **kwargs: None)
    assert narration.fitted({}, Path(), lambda pace: MAX_S + 5) is None
