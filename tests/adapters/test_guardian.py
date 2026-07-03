from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import guardian


@patch("src.adapters.guardian.requests.get")
def test_fetch_articles_returns_webtitles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {
            "response": {
                "results": [
                    {"webTitle": "The best pasta in Rome"},
                    {"webTitle": "Fitness trend: cold plunges"},
                ]
            }
        },
    )

    result = guardian.fetch_articles("lifestyle", limit=5)

    assert result == ["The best pasta in Rome", "Fitness trend: cold plunges"]


@patch("src.adapters.guardian.requests.get")
def test_fetch_articles_returns_empty_on_error(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=403, text="forbidden")

    assert guardian.fetch_articles("food") == []
