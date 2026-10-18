"""Reject scene and caption text that talks about the evidence instead of the subject.

A model that knows its evidence is a headline sometimes says so on screen ("the summary omits
species and baseline details"). Viewers never see the source records, so text like that reads
as a broken post. Each match becomes a repair instruction; a second miss fails the slot.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

META = re.compile(
    r"\b(?:"
    r"summar(?:y|ies|ised|ized)"
    r"|excerpts?"
    r"|headlines?"
    r"|(?:the|this|that) (?:article|record|excerpt|snippet|evidence)"
    # "the source system" and "the source code" are ordinary tech words; only flag the
    # source when the text says what it reports or leaves out.
    r"|(?:the|this|that) source (?:says|said|states|stated|notes|noted|mentions|mentioned"
    r"|reports|reported|describes|lists|gives|omits|leaves|lacks|does(?:n't| not)"
    r"|did(?:n't| not)|is (?:unclear|silent|vague))"
    r"|omit(?:s|ted)?"
    r"|not (?:stated|specified|mentioned|given|reported|provided|disclosed)"
    r"|(?:no|without) (?:details?|specifics|baseline)"
    r"|details? (?:are|is) (?:missing|unclear|unavailable|not given)"
    r")\b",
    re.IGNORECASE,
)


def _strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def meta_commentary(scene: dict[str, Any], caption: str) -> list[str]:
    """Problems for every field that describes the source records instead of the subject."""
    problems = []
    for path, text in [*_strings(scene, "scene"), ("caption", caption)]:
        if match := META.search(text):
            problems.append(
                f'{path} says "{match.group(0)}": write about the subject itself; never mention '
                "the summary, article, headline, excerpt or what the source leaves out"
            )
    return problems
