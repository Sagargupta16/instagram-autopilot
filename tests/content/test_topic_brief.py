"""Topic identity and source provenance must survive generation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.content import topic


@pytest.fixture(autouse=True)
def no_sources_or_history():
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=[]),
        patch("src.content.topic.load_posted_topics", return_value=[]),
    ):
        yield


def test_rejects_normalized_duplicate_from_entire_history(sample_pillar):
    history = ["Pack a café day bag"] + [f"Other topic {i}" for i in range(60)]
    with (
        patch("src.content.topic.load_posted_topics", return_value=history),
        patch(
            "src.content.topic.invoke_claude",
            side_effect=[
                json.dumps({"topic": "  PACK a cafe\u0301 day BAG!!!  "}),
                json.dumps({"topic": "Build a rainy afternoon itinerary"}),
            ],
        ) as model,
    ):
        assert topic.generate_topic(sample_pillar, "guide") == "Build a rainy afternoon itinerary"
    assert model.call_count == 2


@pytest.mark.parametrize(
    "raw", ['{"topic": "  "}', '{"topic": "!!!"}', '{"topic": 42}', "[]", "broken"]
)
def test_invalid_topic_is_repaired(raw, sample_pillar):
    with patch(
        "src.content.topic.invoke_claude", side_effect=[raw, '{"topic": "A packing checklist"}']
    ):
        assert topic.generate_topic(sample_pillar, "guide") == "A packing checklist"


def test_duplicate_repair_is_bounded(sample_pillar):
    with (
        patch("src.content.topic.load_posted_topics", return_value=["Packing list"]),
        patch(
            "src.content.topic.invoke_claude", return_value='{"topic": "PACKING LIST!"}'
        ) as model,
        pytest.raises(ValueError, match="duplicate"),
    ):
        topic.generate_topic(sample_pillar, "guide")
    assert model.call_count == 2


def test_brief_resolves_only_selected_sources(sample_pillar):
    sources = [
        {"title": "Laptop launches", "source": "google_news"},
        {
            "title": "Repair a laptop",
            "source": "guardian",
            "url": "https://example.org/repair",
            "published_at": "2026-09-19",
            "excerpt": "Check the service manual before buying a replacement.",
        },
    ]
    with (
        patch("src.content.topic.fetch_trending_topics", return_value=sources),
        patch(
            "src.content.topic.invoke_claude",
            return_value='{"topic": "Check repairability before replacing a laptop", "source_indices": [1]}',
        ),
    ):
        brief = topic.generate_topic_brief(sample_pillar, "guide")
    assert brief == {
        "topic": "Check repairability before replacing a laptop",
        "sources": [sources[1]],
    }


def test_brief_cannot_invent_source_indices(sample_pillar):
    with (
        patch(
            "src.content.topic.invoke_claude",
            side_effect=[
                '{"topic": "Packing", "source_indices": [99]}',
                '{"topic": "A simple packing checklist", "source_indices": []}',
            ],
        ),
    ):
        assert topic.generate_topic_brief(sample_pillar, "guide")["sources"] == []


@pytest.mark.parametrize("indices", [[-1], [True], [0, 0], ["0"]])
def test_rejects_invalid_source_references(indices, sample_pillar):
    with (
        patch(
            "src.content.topic.fetch_trending_topics",
            return_value=[{"title": "Packing checklist", "source": "guardian"}],
        ),
        patch(
            "src.content.topic.invoke_claude",
            return_value=json.dumps({"topic": "A packing checklist", "source_indices": indices}),
        ),
        pytest.raises(ValueError),
    ):
        topic.generate_topic_brief(sample_pillar, "guide")
