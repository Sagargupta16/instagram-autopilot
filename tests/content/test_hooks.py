"""Stat Reels keep their figure out of the opening, so the count-up stays the reveal."""

from __future__ import annotations

from src.content.hooks import spent_hook

STAT = {
    "kind": "stat",
    "variant": "big_number",
    "headline": "Water bills climbed fast",
    "value": "62%",
}


def test_an_opening_that_leaves_the_figure_to_the_reel_passes() -> None:
    caption = "Water bills climbed faster than wages.\nThey rose 62% in a decade."
    assert spent_hook(STAT, caption) == []


def test_a_headline_or_first_line_with_the_figure_is_sent_back() -> None:
    scene = {**STAT, "headline": "Water bills rose 62%"}
    problems = spent_hook(scene, "In 2025, 62% of bills rose.\nMore context.")
    assert [problem.split(" ")[0] for problem in problems] == ["scene.headline", "the"]
    assert all("gives away 62" in problem for problem in problems)


def test_bar_and_point_values_count_and_grouping_commas_do_not_hide_them() -> None:
    scene = {
        "kind": "stat",
        "variant": "bars",
        "headline": "Which team ships most",
        "bars": [{"label": "Web", "value": "1,530"}, {"label": "Mobile", "value": "860"}],
    }
    assert spent_hook(scene, "Web shipped 1530 times.") != []
    assert spent_hook(scene, "One team ships far more than the rest.") == []


def test_other_formats_and_other_numbers_are_left_alone() -> None:
    assert spent_hook({"kind": "steps", "hook": "How 5 steps ship code"}, "62% faster") == []
    assert spent_hook(STAT, "In 2025, water bills climbed fast.") == []
