from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import google_news

_RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Best hidden beaches in Bali</title><link>https://ex.com/1</link></item>
  <item><title>Tokyo food tour reveals hidden gem</title><link>https://ex.com/2</link></item>
</channel></rss>"""


@patch("src.adapters.google_news.requests.get")
def test_fetch_headlines_parses_rss_items(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True, status_code=200, text=_RSS_SAMPLE)

    result = google_news.fetch_headlines("travel", limit=5)

    assert result == ["Best hidden beaches in Bali", "Tokyo food tour reveals hidden gem"]


@patch("src.adapters.google_news.requests.get")
def test_fetch_headlines_returns_empty_on_error(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=429, text="throttled")

    assert google_news.fetch_headlines("food") == []


@patch("src.adapters.google_news.requests.get")
def test_fetch_headlines_returns_empty_on_bad_xml(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True, status_code=200, text="<not xml")

    assert google_news.fetch_headlines("tech") == []
