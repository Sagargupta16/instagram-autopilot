"""Refuse a topic that restates a recent one in different words.

The exact-wording check misses "One in four new cars sold worldwide in 2025 was electric"
against "1 in 4 new cars sold worldwide in 2025 was electric", which would have repeated
the 2026-10-16 post. Topics are compared as sets of content words (stop words dropped,
simple plurals folded); a new topic is too close when at least NEAR of the smaller set's
words also appear in the other. Measured on the last 100 real topics: no pair among them
reaches 0.7, and the EV restatement scores 1.0.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

NEAR = 0.75
MIN_WORDS = 4  # shorter topics are too generic to compare by overlap; the exact check covers them
STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "from",
        "by",
        "with",
        "without",
        "into",
        "onto",
        "over",
        "under",
        "about",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "your",
        "you",
        "our",
        "we",
        "they",
        "their",
        "how",
        "what",
        "why",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "may",
        "might",
        "must",
        "not",
        "no",
        "yes",
        "than",
        "then",
        "so",
        "too",
        "very",
        "just",
        "more",
        "most",
        "less",
        "least",
        "here",
        "there",
        "up",
        "down",
        "out",
        "off",
        "one",
        "two",
        "three",
    ]
)


def words(topic: str) -> frozenset[str]:
    """Content words of a topic, lowercased, stop words dropped and plurals folded."""
    out = set()
    for word in re.findall(r"[a-z0-9]+", topic.casefold()):
        if word in STOP or len(word) < 2:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.add(word)
    return frozenset(out)


def near_repeat(topic: str, posted: Iterable[str]) -> str | None:
    """The most recent posted topic this one restates, or None."""
    new = words(topic)
    for old in reversed(list(posted)):
        prior = words(old)
        smaller = min(len(new), len(prior))
        if smaller >= MIN_WORDS and len(new & prior) / smaller >= NEAR:
            return old
    return None
