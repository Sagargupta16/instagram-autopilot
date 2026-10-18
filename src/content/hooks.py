"""Reject weak Reel openers before rendering: the hook is the first frame and the first words.

The rules are the unambiguous failures from Jake Schincariol's hook scorer
(github.com/Jakeschincariol/instagram-agent-skill, MIT): a greeting, a video preamble, a plea
for attention, filler, a hashtag or an emoji. That project's own test found its scorer catches
bad hooks well but cannot pick winners, so only these hard failures are enforced, never a
score. Openers match whole words, so "your" never trips "you" (its issue #17).
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
