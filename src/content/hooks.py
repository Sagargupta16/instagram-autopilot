"""Reject weak Reel openers before rendering: the hook is the first frame and the first words.

The rules are the unambiguous failures from Jake Schincariol's hook scorer
(github.com/Jakeschincariol/instagram-agent-skill, MIT): a greeting, a video preamble, a plea
for attention, filler, a hashtag or an emoji. That project's own test found its scorer catches
bad hooks well but cannot pick winners, so only these hard failures are enforced, never a
score. Openers match whole words, so "your" never trips "you" (its issue #17).

Stat Reels must also keep their figure out of the headline and the caption's first line, so
the count-up is the reveal: the account's three stat Reels that opened on the figure lost
87.5 to 100% of viewers in the first three seconds (Instagram insights, read 2026-10-24).
"""

from __future__ import annotations

import re
from typing import Any

RULES = (
    (re.compile(r"^\s*(?:stop scrolling|don'?t scroll)\b", re.IGNORECASE), "asks for attention"),
    (
        re.compile(
            r"\b(?:in (?:this|today'?s) (?:video|reel|post)|i'?m going to show you|i'?ll show you"
            r"|let'?s (?:talk about|dive into|look at))\b",
            re.IGNORECASE,
        ),
        "is a preamble",
    ),
    (re.compile(r"^\s*(?:hey|hi|hello|what'?s up|welcome)\b", re.IGNORECASE), "is a greeting"),
    (
        re.compile(r"^\s*(?:so|ok|okay|alright|basically|honestly|um|guys|yo|listen)\b", re.I),
        "opens on filler",
    ),
    (re.compile(r"(?:^|\s)#\w"), "contains a hashtag"),
    (re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]"), "contains an emoji"),
)
HOOK_FIELDS = ("hook", "headline")
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def weak_hook(scene: dict[str, Any]) -> list[str]:
    """One repair instruction for each rule the opening line breaks."""
    problems = []
    for field in HOOK_FIELDS:
        text = scene.get(field)
        if not isinstance(text, str):
            continue
        problems += [
            f'scene.{field} "{text}" {why}: open on the subject itself, as a plain question or '
            "promise; no greeting, filler, preamble, hashtag or emoji"
            for pattern, why in RULES
            if pattern.search(text)
        ]
    return problems


def _figures(text: str) -> set[str]:
    """Every figure in `text` as plain digits: "1,530" and "62%" give "1530" and "62"."""
    return {match.replace(",", "") for match in _FIGURE.findall(text)}


def spent_hook(scene: dict[str, Any], caption: str) -> list[str]:
    """Stat Reels only: one repair instruction for each opening that gives the figure away."""
    if scene.get("kind") != "stat":
        return []
    values = [scene.get("value"), *(item.get("value") for item in scene.get("bars") or [])]
    values += [item.get("value") for item in scene.get("points") or []]
    figures = set().union(*(_figures(value) for value in values if isinstance(value, str)))
    first = caption.strip().split("\n", 1)[0]
    headline = scene.get("headline") or ""
    openings = (("scene.headline", headline), ("the caption's first line", first))
    return [
        f'{where} "{text}" gives away {", ".join(sorted(shown))}: name the subject and what is '
        "surprising about it, and let the Reel reveal the figure (the caption states it after "
        "the first line)"
        for where, text in openings
        if (shown := _figures(text) & figures)
    ]
