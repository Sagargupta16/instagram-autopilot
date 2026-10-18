"""Scene and caption text must describe the subject, never the source records."""

from __future__ import annotations

from typing import Any

import pytest

from src.content.voice import meta_commentary

STAT = {
    "kind": "stat",
    "variant": "big_number",
    "headline": "A rare Texas shark population",
    "value": "99%",
    "context": "reported decline of a rare Texas shark, per Chron",
    "takeaway": "Almost the whole population is gone.",
    "source_index": 0,
}


def _with(**overrides: Any) -> dict[str, Any]:
    return {**STAT, **overrides}


def test_subject_text_and_attribution_pass() -> None:
    assert meta_commentary(STAT, "A rare Texas shark has declined 99%, per Chron.") == []


def test_the_published_shark_takeaway_is_rejected() -> None:
    # 2026-10-11 offline render of a live model scene put this on the final frame.
    scene = _with(takeaway="A near-total drop; the summary omits species and baseline details.")
    problems = meta_commentary(scene, "")
    assert len(problems) == 1
    assert problems[0].startswith('scene.takeaway says "summary"')


@pytest.mark.parametrize(
    "text",
    [
        "The article does not give a date.",
        "The headline reports a drop.",
        "The excerpt lists two figures.",
        "The cause is not stated.",
        "Shared without details on the method.",
        "Details are missing for 2024.",
        "This record covers one state.",
        "The source does not give a date.",
        "The source says the drop was steep.",
    ],
)
def test_meta_phrases_are_rejected_in_any_field(text: str) -> None:
    assert meta_commentary(_with(context=text), "") != []


@pytest.mark.parametrize(
    "text",
    [
        "Open source tools ship faster.",
        "The data source is public.",
        "The source system sends a POST to your URL.",  # live 2026-10-18 webhook explainer
        "The source app signs each event.",
    ],
)
def test_ordinary_tech_words_are_not_flagged(text: str) -> None:
    assert meta_commentary(_with(context=text), text) == []


def test_nested_fields_and_the_caption_are_checked() -> None:
    steps = {
        "kind": "steps",
        "hook": "How does DNS work?",
        "steps": [{"label": "Ask", "detail": "Not specified in the source."}],
        "takeaway": "Names become addresses.",
    }
    problems = meta_commentary(steps, "The summary is short.")
    assert [problem.split(" says ")[0] for problem in problems] == [
        "scene.steps[0].detail",
        "caption",
    ]
