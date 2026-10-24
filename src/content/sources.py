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


PUBLICATIONS = {
    "github": "GitHub",
    "google_news": "Google News",
    "guardian": "The Guardian",
    "hackernews": "Hacker News",
    "huggingface": "Hugging Face Papers",
    "lemmy": "Lemmy",
    "producthunt": "Product Hunt",
    "wikipedia": "Wikipedia",
}


def publication_name(record: dict[str, str]) -> str:
    """Display name from adapter metadata only; model text never names a source."""
    return record.get("publisher") or PUBLICATIONS.get(record.get("source", ""), "") or "the source"


def _web_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def _field(key: str, value: object, excerpt_limit: int) -> str | None:
    """One metadata value as a record keeps it, or None to leave it out."""
    if not isinstance(value, str) or not value.strip():
        return None
    if key == "url":
        return value.strip() if _web_url(value) else None
    if key == "excerpt":
        return plain_text(value, excerpt_limit) or None
    if key == "publisher":
        return plain_text(value, 80) or None
    return value.strip()


def source_record(
    title: str, source: str, category: str, *, excerpt_limit: int = 800, **metadata: object
) -> dict[str, str]:
    """Omit missing values; never substitute fetch time for publication time."""
    record = {"title": plain_text(title, 500), "source": source, "category": category}
    for key in ("url", "published_at", "updated_at", "observed_at", "excerpt", "publisher"):
        if (text := _field(key, metadata.get(key), excerpt_limit)) is not None:
            record[key] = text
    return record


def records_or_titles(
    records: list[dict[str, str]], include_metadata: bool
) -> list[dict[str, str]] | list[str]:
    records = [record for record in records if record["title"]]
    return records if include_metadata else [record["title"] for record in records]
