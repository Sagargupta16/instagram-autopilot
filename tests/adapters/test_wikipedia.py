from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from src.adapters import wikipedia


@patch("src.adapters.wikipedia.requests.get")
def test_fetch_top_articles_returns_titles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {
            "items": [
                {
                    "articles": [
                        {"article": "OpenAI"},
                        {"article": "Main_Page"},
                        {"article": "Special:Search"},
                        {"article": "Bali"},
                    ]
                }
            ]
        },
    )

    result = wikipedia.fetch_top_articles(limit=10)

    assert result == ["OpenAI", "Bali"]


@patch("src.adapters.wikipedia.requests.get")
def test_fetch_top_articles_falls_back_on_404(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=404, text="Not Found")

    assert wikipedia.fetch_top_articles() == []


@patch("src.adapters.wikipedia.requests.get")
def test_fetch_top_articles_swallows_network_error(mock_get: Mock) -> None:
    import requests as _r

    mock_get.side_effect = _r.ConnectionError("boom")

    assert wikipedia.fetch_top_articles() == []


def _fake_get(articles: list[str], extracts: object):
    """Pageviews always succeed; the extracts call returns or raises `extracts`."""

    def get(url: str, params: dict | None = None, **kwargs: object) -> Mock:
        if url != wikipedia._EXTRACTS_URL:
            payload = {"items": [{"articles": [{"article": name} for name in articles]}]}
            return Mock(ok=True, status_code=200, json=lambda: payload)
        if isinstance(extracts, BaseException):
            raise extracts
        if isinstance(extracts, Mock):
            return extracts
        return Mock(ok=True, status_code=200, json=lambda: {"query": extracts})

    return get


@patch("src.adapters.wikipedia.requests.get")
def test_extracts_merge_through_normalized_and_redirected_titles(mock_get: Mock) -> None:
    mock_get.side_effect = _fake_get(
        ["Apollo_11", "Nasa", "moon_landing", "Bali"],
        {
            "normalized": [{"from": "moon landing", "to": "Moon landing"}],
            "redirects": [{"from": "Nasa", "to": "NASA"}],
            "pages": [
                {"title": "Apollo 11", "extract": "Apollo 11 landed on 20 July 1969."},
                {"title": "NASA", "extract": "NASA was founded in 1958."},
                {"title": "Moon landing", "extract": "The first crewed landing was in 1969."},
                {"title": "Bali", "missing": True},
            ],
        },
    )

    records = wikipedia.fetch_top_articles_with_extracts(10, include_metadata=True)

    assert {record["title"]: record.get("excerpt") for record in records} == {
        "Apollo 11": "Apollo 11 landed on 20 July 1969.",
        "Nasa": "NASA was founded in 1958.",
        "moon landing": "The first crewed landing was in 1969.",
        "Bali": None,
    }
    assert all(record["source"] == "wikipedia" and "observed_at" in record for record in records)
    assert records[0]["url"] == "https://en.wikipedia.org/wiki/Apollo_11"
    params = mock_get.call_args_list[-1].kwargs["params"]
    assert params["titles"] == "Apollo 11|Nasa|moon landing|Bali"
    assert params["exintro"] == params["explaintext"] == params["redirects"] == 1


@patch("src.adapters.wikipedia.requests.get")
def test_extract_is_kept_up_to_extract_chars(mock_get: Mock) -> None:
    text = "Apollo 11 landed in 1969. " + "x" * (wikipedia.EXTRACT_CHARS * 2)
    mock_get.side_effect = _fake_get(
        ["Apollo_11"], {"pages": [{"title": "Apollo 11", "extract": text}]}
    )

    [record] = wikipedia.fetch_top_articles_with_extracts(include_metadata=True)

    assert len(record["excerpt"]) == wikipedia.EXTRACT_CHARS > 800
    assert record["excerpt"] == text[: wikipedia.EXTRACT_CHARS]


@pytest.mark.parametrize(
    "failure",
    [requests.ConnectionError("boom"), Mock(ok=False, status_code=503)],
    ids=["network-error", "http-503"],
)
@patch("src.adapters.wikipedia.requests.get")
def test_records_survive_a_failed_extracts_request(mock_get: Mock, failure: object) -> None:
    mock_get.side_effect = _fake_get(["Apollo_11", "Bali"], failure)

    records = wikipedia.fetch_top_articles_with_extracts(include_metadata=True)

    assert [record["title"] for record in records] == ["Apollo 11", "Bali"]
    assert not any("excerpt" in record for record in records)
    assert wikipedia.fetch_top_articles_with_extracts() == ["Apollo 11", "Bali"]


@pytest.mark.parametrize(
    ("articles", "query"),
    [
        (
            ["nasa"],
            {
                "normalized": [{"from": "nasa", "to": "Nasa"}],
                "redirects": [{"from": "Nasa", "to": "NASA"}],
                "pages": [{"title": "NASA", "extract": "NASA was founded in 1958."}],
            },
        ),
        (
            ["Apollo_11", "First_Moon_landing"],
            {
                "redirects": [{"from": "First Moon landing", "to": "Apollo 11"}],
                "pages": [{"title": "Apollo 11", "extract": "Apollo 11 landed in 1969."}],
            },
        ),
    ],
    ids=["normalized-then-redirect", "canonical-and-redirect"],
)
@patch("src.adapters.wikipedia.requests.get")
def test_every_requested_title_gets_its_resolved_extract(
    mock_get: Mock, articles: list[str], query: dict
) -> None:
    mock_get.side_effect = _fake_get(articles, query)

    records = wikipedia.fetch_top_articles_with_extracts(include_metadata=True)

    assert all(record.get("excerpt") for record in records)
