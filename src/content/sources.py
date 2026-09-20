"""Small, loss-conscious records for untrusted trend evidence."""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit


def normalize_topic(text: str) -> str:
    """Match exact wording across Unicode, case, punctuation, and spacing."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.parts.append(" ")


def plain_text(value: object, limit: int = 800) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    parser.feed(value)
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()[:limit]


def source_record(title: str, source: str, category: str, **metadata: object) -> dict[str, str]:
    """Omit missing values; never substitute fetch time for publication time."""
    record = {"title": plain_text(title, 500), "source": source, "category": category}
    for key in ("url", "published_at", "updated_at", "observed_at", "excerpt"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if key == "url":
            try:
                parsed = urlsplit(value)
                if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                    continue
            except ValueError:
                continue
            record[key] = value.strip()
        elif key == "excerpt":
            if text := plain_text(value):
                record[key] = text
        else:
            record[key] = value.strip()
    return record


def records_or_titles(
    records: list[dict[str, str]], include_metadata: bool
) -> list[dict[str, str]] | list[str]:
    records = [record for record in records if record["title"]]
    return records if include_metadata else [record["title"] for record in records]
