"""Number extraction and grounding checks for animated Reel text."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.content.grounding import evidence_text, numbers, published_text, ungrounded


def test_thousands_separators_are_one_number() -> None:
    assert numbers("1,234,567 people") == [Decimal(1234567)]


def test_trailing_decimal_zeros_do_not_change_the_value() -> None:
    assert numbers("3.80") == numbers("3.8") == [Decimal("3.8")]


@pytest.mark.parametrize("text", ["62%", "62 %", "62 per cent", "62 percent", "62 Percent"])
def test_percent_forms_give_the_bare_number(text: str) -> None:
    assert numbers(text) == [Decimal(62)]


def test_multiplier_suffixes_agree_with_the_written_out_figure() -> None:
    assert numbers("2.5 million") == numbers("2.5m") == numbers("2,500,000") == [Decimal(2500000)]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("$1 Billion", Decimal(10) ** 9),
        ("1.2bn", Decimal("1.2") * 10**9),
        ("5k", Decimal(5000)),
        ("3 trillion", Decimal(3) * 10**12),
    ],
)
def test_scale_words_and_abbreviations(text: str, value: Decimal) -> None:
    assert numbers(text) == [value]


def test_raw_also_yields_the_unscaled_figure() -> None:
    assert numbers("2.5 million", raw=True) == [Decimal(2500000), Decimal("2.5")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("four in ten adults", [4, 10]),
        ("a dozen eggs", [12]),
        ("thirty years", [30]),
        ("two keys", [2]),
    ],
)
def test_number_words_are_quantities(text: str, expected: list[int]) -> None:
    assert numbers(text) == [Decimal(value) for value in expected]


def test_iso_dates_split_into_year_month_and_day() -> None:
    assert numbers("published 2026-09-19") == [Decimal(2026), Decimal(9), Decimal(19)]


@pytest.mark.parametrize("text", ["one", "One of the ways", "no one knows", "often tens"])
def test_one_and_partial_words_are_ignored(text: str) -> None:
    assert numbers(text) == []


def test_evidence_text_uses_only_title_and_excerpt() -> None:
    record = {
        "title": "Water bills rose 62%",
        "excerpt": "Over a decade, according to 2,000 utilities.",
        "url": "https://example.org/2024/77/report",
        "publisher": "Example Times 365",
        "published_at": "2025-01-31",
        "source": "google_news",
    }
    text = evidence_text([record])
    assert "Water bills rose 62%" in text
    assert "according to 2,000 utilities" in text
    for field in ("url", "publisher", "published_at", "source"):
        assert record[field] not in text
    assert numbers(text) == [Decimal(62), Decimal(2000)]


def test_evidence_text_tolerates_missing_fields() -> None:
    assert numbers(evidence_text([{"title": "Only a title with 7 words"}, {}])) == [Decimal(7)]


def test_published_text_drops_urls_and_hashtags() -> None:
    text = published_text("Read https://example.org/2024/top-10 now #top10 #2026 then 5")
    assert "2024" not in text
    assert "top10" not in text
    assert "2026" not in text
    assert numbers(text) == [Decimal(5)]
    assert text.split() == ["Read", "now", "then", "5"]


def test_ungrounded_lists_missing_numbers_once_in_order() -> None:
    evidence = "U.S. drinking water bills rose 62% in a decade"
    texts = ["Bills rose 64% in 10 years", "That is 64 percent"]
    assert ungrounded(texts, evidence) == ["64", "10"]


def test_ungrounded_is_empty_when_every_number_is_present() -> None:
    evidence = "Bills rose 62% from 1,240 in 2015 to $2.5 million"
    texts = ["62 per cent", "1240", "2015", "2.5m", "$2,500,000"]
    assert ungrounded(texts, evidence) == []


def test_raw_value_is_supported_by_scaled_evidence() -> None:
    assert ungrounded(["2.5"], "Sales reached 2.5 million") == []
    assert ungrounded(["2.6"], "Sales reached 2.5 million") == ["2.6"]


def test_scaled_claim_is_not_supported_by_its_bare_figure() -> None:
    assert ungrounded(["2.5 million"], "a rating of 2.5 stars") == ["2500000"]


def test_ungrounded_labels_are_plain_decimals() -> None:
    assert ungrounded(["for every 100 people in 1990"], "") == ["100", "1990"]
