"""A topic that restates a recent post in new words is refused before any paid generation."""

from __future__ import annotations

import pytest

from src.content.novelty import near_repeat

# The 2026-10-16 post, and the 2026-10-19 topic that restated it.
POSTED = "1 in 4 new cars sold worldwide in 2025 was electric \u2014 see the share climb"
RESTATED = "One in four new cars sold worldwide in 2025 was electric \u2014 watch the global EV share climb"


def test_a_restated_fact_is_caught() -> None:
    assert near_repeat(RESTATED, ["How DNS finds a website", POSTED]) == POSTED


@pytest.mark.parametrize(
    "topic",
    [
        "Electric buses in Europe: who leads in 2025",
        "How a webhook works: a 5-step walk from event trigger to your app",
        "The story of the Hubble Space Telescope",
    ],
)
def test_a_related_but_different_topic_passes(topic: str) -> None:
    assert near_repeat(topic, [POSTED, "The story of Hubble", "How DNS finds a website"]) is None


def test_short_topics_are_left_to_the_exact_check() -> None:
    assert near_repeat("How DNS works", ["How DNS caching works"]) is None
