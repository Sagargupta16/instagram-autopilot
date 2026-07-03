"""Tests for posting-schedule jitter + plan_today."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from src import schedule
from src.schedule import apply_jitter, plan_today


class TestApplyJitter:
    def test_zero_max_does_not_sleep(self) -> None:
        with patch("src.schedule.time.sleep") as mock_sleep:
            apply_jitter(0)
            mock_sleep.assert_not_called()

    def test_sleeps_within_bounds(self) -> None:
        with patch("src.schedule.time.sleep") as mock_sleep:
            with patch("src.schedule.random.randint", return_value=300):
                apply_jitter(10)
            mock_sleep.assert_called_once_with(300)

    def test_negative_max_does_not_sleep(self) -> None:
        with patch("src.schedule.time.sleep") as mock_sleep:
            apply_jitter(-5)
            mock_sleep.assert_not_called()


def test_to_minutes_parses_hhmm() -> None:
    assert schedule.to_minutes("04:00") == 240
    assert schedule.to_minutes("20:30") == 1230


def test_to_hhmm_formats_minutes() -> None:
    assert schedule.to_hhmm(240) == "04:00"
    assert schedule.to_hhmm(1230) == "20:30"


_PILLARS = [{"id": "a", "weight": 1.0}, {"id": "b", "weight": 2.0}]
_CADENCE_N2 = {
    "max_posts_per_day": 3,
    "post_probability": [0.0, 0.0, 1.0, 0.0],
    "window_utc": {"start": "04:00", "end": "20:00"},
    "min_gap_minutes": 90,
    "skip_probability": 0.0,
}


def test_plan_today_deterministic_per_date() -> None:
    d = date(2026, 7, 3)
    assert plan_today(d, _CADENCE_N2, _PILLARS) == plan_today(d, _CADENCE_N2, _PILLARS)


def test_plan_today_differs_across_dates() -> None:
    p1 = plan_today(date(2026, 7, 3), _CADENCE_N2, _PILLARS)
    p2 = plan_today(date(2026, 7, 4), _CADENCE_N2, _PILLARS)
    assert p1 != p2


def test_plan_respects_max_posts_per_day() -> None:
    forced_5 = {**_CADENCE_N2, "post_probability": [0, 0, 0, 0, 1.0], "max_posts_per_day": 3}
    plan = plan_today(date(2026, 7, 3), forced_5, _PILLARS)
    assert len(plan) <= 3


def test_plan_respects_min_gap() -> None:
    from itertools import pairwise

    plan = plan_today(date(2026, 7, 3), _CADENCE_N2, _PILLARS)
    for a, b in pairwise(plan):
        assert schedule.to_minutes(b.time_utc) - schedule.to_minutes(a.time_utc) >= 90


def test_plan_zero_posts_returns_empty() -> None:
    always_zero = {**_CADENCE_N2, "post_probability": [1.0, 0.0, 0.0, 0.0]}
    assert plan_today(date(2026, 7, 3), always_zero, _PILLARS) == []


def test_plan_empty_pillars_returns_empty() -> None:
    assert plan_today(date(2026, 7, 3), _CADENCE_N2, []) == []
