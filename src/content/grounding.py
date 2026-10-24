"""Every number shown on screen must already appear in the adapters' evidence text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_SUFFIX = re.compile(
    r"\s?(?:(%)|(per\s?cent|percent)\b|(k|thousand)\b|(m|mn|million)\b|(b|bn|billion)\b|"
    r"(tn|trillion)\b)",
    re.IGNORECASE,
)
_SCALE = {3: Decimal(10) ** 3, 4: Decimal(10) ** 6, 5: Decimal(10) ** 9, 6: Decimal(10) ** 12}
_WORDS = (
    {
        word: Decimal(value)
        for value, word in enumerate(
            (
                "zero",
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
                "ten",
                "eleven",
                "twelve",
                "thirteen",
                "fourteen",
                "fifteen",
                "sixteen",
                "seventeen",
                "eighteen",
                "nineteen",
                "twenty",
            )
        )
        if value >= 2  # "one" is ordinary prose far more often than a quantity
    }
    | {
        word: Decimal(value * 10)
        for value, word in enumerate(
            ("", "", "", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
        )
        if value >= 3
    }
    | {
        "dozen": Decimal(12),
        "hundred": Decimal(100),
        "thousand": Decimal(10) ** 3,
        "million": Decimal(10) ** 6,
        "billion": Decimal(10) ** 9,
        "trillion": Decimal(10) ** 12,
    }
)
_WORD = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")
_HASHTAG = re.compile(r"#\w+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_BLANKS = re.compile(r"\n{3,}")


def _value(token: str) -> Decimal | None:
    """1,234,567 -> 1234567; 3.80 -> 3.8; a comma that is not a thousands separator splits."""
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
        token = token.replace(",", "")
    if "," in token or token.count(".") > 1:
        return None
    try:
        return Decimal(token).normalize()
    except InvalidOperation:
        return None


def _parts(token: str) -> list[str]:
    if _value(token) is not None:
        return [token]
    return [part for part in re.split(r"[.,]", token) if part]


def numbers(text: str, *, raw: bool = False) -> list[Decimal]:
    """Quantities in text, with thousand/million/billion/trillion suffixes applied.

    raw=True also yields each unscaled figure, so evidence reading "2.5 million" supports a
    chart value of 2.5 whose unit is shown separately.
    """
    found = [value for match in _NUMBER.finditer(text) for value in _figures(text, match, raw)]
    return found + _spelled(text)


def _figures(text: str, match: re.Match[str], raw: bool) -> list[Decimal]:
    """The digits of one match, with a following thousand, million (...) suffix applied."""
    found: list[Decimal] = []
    parts = _parts(match.group())
    for index, part in enumerate(parts):
        value = _value(part)
        if value is None:
            continue
        suffix = _SUFFIX.match(text, match.end()) if index == len(parts) - 1 else None
        group = next((i for i in range(3, 7) if suffix and suffix.group(i)), None)
        if group is None:
            found.append(value)
            continue
        found.append((value * _SCALE[group]).normalize())
        if raw:
            found.append(value)
    return found


def _spelled(text: str) -> list[Decimal]:
    """Number words, skipping a scale word that already scaled the digits before it."""
    found: list[Decimal] = []
    for match in _WORD.finditer(text):
        word = match.group().casefold()
        before = text[max(0, match.start() - 2) : match.start()]
        if word in {"thousand", "million", "billion", "trillion"} and re.search(r"\d\s?$", before):
            continue  # already applied as a suffix
        found.append(_WORDS[word].normalize())
    return found


def evidence_text(sources: Iterable[dict]) -> str:
    """The adapter-returned text: titles and excerpts, never model-authored metadata."""
    return "\n".join(
        str(source.get(field, "")) for source in sources for field in ("title", "excerpt")
    )


def published_text(text: str) -> str:
    """Caption text a reader sees, without links and hashtags (their digits are not claims)."""
    return _HASHTAG.sub(" ", _URL.sub(" ", text))


def ungrounded(texts: Iterable[str], evidence: str) -> list[str]:
    """Numbers in texts that the evidence does not contain, formatted for a repair prompt."""
    supported = set(numbers(evidence, raw=True))
    missing: list[str] = []
    for text in texts:
        for value in numbers(text):
            label = format(value, "f")
            if value not in supported and label not in missing:
                missing.append(label)
    return missing


def verified_caption(raw: object, *, sources: list[dict]) -> dict | None:
    """A copy of model output whose caption keeps only the sentences whose numbers the
    evidence contains, or None when nothing would go or nothing would be left.

    The last resort after the repair calls: removing a sentence never adds a claim, so what
    is left can only be verified facts (it must still pass every other check).
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("caption"), str):
        return None
    evidence = evidence_text(sources)
    lines, dropped = [], 0
    for line in raw["caption"].split("\n"):
        sentences = [part for part in _SENTENCE.split(line) if part.strip()]
        kept = [part for part in sentences if not ungrounded([published_text(part)], evidence)]
        dropped += len(sentences) - len(kept)
        if kept or not sentences:
            lines.append(" ".join(kept))
    caption = _BLANKS.sub("\n\n", "\n".join(lines)).strip()
    if not dropped or not caption:
        return None
    return {**raw, "caption": caption}
