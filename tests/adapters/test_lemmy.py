from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import lemmy


@patch("src.adapters.lemmy.requests.get")
def test_fetch_hot_posts_returns_titles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {
            "posts": [
                {"post": {"name": "Sourdough discovery"}},
                {"post": {"name": "New running app tested"}},
            ]
        },
    )

    result = lemmy.fetch_hot_posts("food")

    assert result == ["Sourdough discovery", "New running app tested"]


@patch("src.adapters.lemmy.requests.get")
def test_fetch_hot_posts_falls_back_to_next_instance(mock_get: Mock) -> None:
    mock_get.side_effect = [
        Mock(ok=False, status_code=503, text="down"),
        Mock(
            ok=True,
            status_code=200,
            json=lambda: {"posts": [{"post": {"name": "Fallback title"}}]},
        ),
    ]

    result = lemmy.fetch_hot_posts("food")

    assert result == ["Fallback title"]
    assert mock_get.call_count == 2


@patch("src.adapters.lemmy.requests.get")
def test_fetch_hot_posts_returns_empty_when_all_instances_fail(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=503, text="down")

    assert lemmy.fetch_hot_posts("food") == []
