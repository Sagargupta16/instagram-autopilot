"""Tests for posting-schedule jitter."""

from __future__ import annotations

from unittest.mock import patch

from src.schedule import apply_jitter


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
