from __future__ import annotations

from unittest.mock import Mock, patch

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
