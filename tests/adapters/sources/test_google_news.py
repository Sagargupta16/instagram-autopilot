from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters.sources import google_news

_RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Best hidden beaches in Bali</title><link>https://ex.com/1</link></item>
  <item><title>Tokyo food tour reveals hidden gem</title><link>https://ex.com/2</link></item>
</channel></rss>"""


@patch("src.adapters.sources.google_news.requests.get")
def test_fetch_headlines_parses_rss_items(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True, status_code=200, text=_RSS_SAMPLE)

    result = google_news.fetch_headlines("travel", limit=5)

    assert result == ["Best hidden beaches in Bali", "Tokyo food tour reveals hidden gem"]


@patch("src.adapters.sources.google_news.requests.get")
def test_fetch_headlines_returns_empty_on_error(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=429, text="throttled")

    assert google_news.fetch_headlines("food") == []


@patch("src.adapters.sources.google_news.requests.get")
def test_fetch_headlines_returns_empty_on_bad_xml(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True, status_code=200, text="<not xml")

    assert google_news.fetch_headlines("tech") == []


_RSS_WITH_SOURCE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Water bills rose 62% in a decade - Reuters</title>
    <link>https://news.google.com/rss/articles/abc</link>
    <pubDate>Fri, 19 Sep 2026 10:00:00 GMT</pubDate>
    <source url="https://www.reuters.com">Reuters</source>
  </item>
  <item><title>Untitled wire story</title><link>https://ex.com/2</link></item>
</channel></rss>"""


@patch("src.adapters.sources.google_news.requests.get")
def test_rss_source_element_becomes_the_publisher(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True, status_code=200, text=_RSS_WITH_SOURCE)

    first, second = google_news.fetch_headlines("survey percent", include_metadata=True)

    assert first["publisher"] == "Reuters"
    assert first["source"] == "google_news"
    assert first["published_at"] == "Fri, 19 Sep 2026 10:00:00 GMT"
    assert "publisher" not in second
