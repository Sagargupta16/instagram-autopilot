"""Preserve actual feed evidence; absent metadata must remain absent."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.adapters import (
    github_trending,
    google_news,
    guardian,
    hackernews,
    huggingface_papers,
    lemmy,
    producthunt,
    wikipedia,
)


@pytest.mark.parametrize(
    ("module", "function", "args", "payload", "expected"),
    [
        (
            github_trending,
            "fetch_trending",
            (),
            {
                "items": [
                    {
                        "name": "repair",
                        "description": "A repair guide",
                        "html_url": "https://github.com/example/repair",
                        "pushed_at": "2026-09-19",
                    }
                ]
            },
            {
                "title": "repair: A repair guide",
                "source": "github",
                "category": "technology",
                "excerpt": "A repair guide",
                "url": "https://github.com/example/repair",
                "updated_at": "2026-09-19",
            },
        ),
        (
            guardian,
            "fetch_articles",
            ("food",),
            {
                "response": {
                    "results": [
                        {
                            "webTitle": "Make soup",
                            "webUrl": "https://example.org/soup",
                            "webPublicationDate": "2026-09-19",
                            "fields": {"trailText": "<p>Use seasonal vegetables.</p>"},
                        }
                    ]
                }
            },
            {
                "title": "Make soup",
                "source": "guardian",
                "category": "food",
                "url": "https://example.org/soup",
                "published_at": "2026-09-19",
                "excerpt": "Use seasonal vegetables.",
            },
        ),
        (
            hackernews,
            "search_stories",
            ("technology",),
            {
                "hits": [
                    {
                        "title": "Repair tools",
                        "url": "https://example.org/tools",
                        "created_at": "2026-09-19",
                        "story_text": "Check the <b>manual</b>.",
                    }
                ]
            },
            {
                "title": "Repair tools",
                "source": "hackernews",
                "category": "technology",
                "url": "https://example.org/tools",
                "published_at": "2026-09-19",
                "excerpt": "Check the manual.",
            },
        ),
        (
            huggingface_papers,
            "fetch_daily_papers",
            (),
            [
                {
                    "paper": {
                        "title": "A research paper",
                        "id": "2609.01234",
                        "publishedAt": "2026-09-19",
                        "summary": "A small benchmark study.",
                    }
                }
            ],
            {
                "title": "A research paper",
                "source": "huggingface",
                "category": "technology",
                "url": "https://huggingface.co/papers/2609.01234",
                "published_at": "2026-09-19",
                "excerpt": "A small benchmark study.",
            },
        ),
        (
            lemmy,
            "fetch_hot_posts",
            ("travel",),
            {
                "posts": [
                    {
                        "post": {
                            "name": "Packing question",
                            "url": "https://example.org/bag",
                            "published": "2026-09-19",
                            "body": "Which pocket holds a bottle?",
                        }
                    }
                ]
            },
            {
                "title": "Packing question",
                "source": "lemmy",
                "category": "travel",
                "url": "https://example.org/bag",
                "published_at": "2026-09-19",
                "excerpt": "Which pocket holds a bottle?",
            },
        ),
    ],
)
def test_json_sources_preserve_provenance(module, function, args, payload, expected):
    with patch.object(module.requests, "get", return_value=Mock(ok=True, json=lambda: payload)):
        assert getattr(module, function)(*args, include_metadata=True) == [expected]


def test_google_rss_preserves_source_fields():
    rss = """<rss><channel><item><title>A day bag</title>
    <link>https://example.org/bag</link><pubDate>Sat, 19 Sep 2026 12:00:00 GMT</pubDate>
    <description>&lt;p&gt;Pack a bottle &amp;amp; a layer.&lt;/p&gt;</description>
    </item><item><title>Title only</title></item></channel></rss>"""
    with patch.object(google_news.requests, "get", return_value=Mock(ok=True, text=rss)):
        records = google_news.fetch_headlines("travel", include_metadata=True)
    assert records == [
        {
            "title": "A day bag",
            "source": "google_news",
            "category": "travel",
            "url": "https://example.org/bag",
            "published_at": "Sat, 19 Sep 2026 12:00:00 GMT",
            "excerpt": "Pack a bottle & a layer.",
        },
        {"title": "Title only", "source": "google_news", "category": "travel"},
    ]


def test_atom_selects_article_link_and_preserves_summary():
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A tool</title>
    <link rel="self" href="https://example.org/api"/><link rel="alternate" href="https://example.org/tool"/>
    <published>2026-09-19</published><summary>Compare a &lt;b&gt;workflow&lt;/b&gt;.</summary>
    </entry></feed>"""
    with patch.object(producthunt.requests, "get", return_value=Mock(text=atom)):
        assert producthunt.fetch_ai_launches(include_metadata=True) == [
            {
                "title": "A tool",
                "source": "producthunt",
                "category": "technology",
                "url": "https://example.org/tool",
                "published_at": "2026-09-19",
                "excerpt": "Compare a workflow.",
            }
        ]


def test_wikipedia_pageview_date_is_not_article_publication_date():
    payload = {"items": [{"articles": [{"article": "Bali"}]}]}
    with patch.object(wikipedia.requests, "get", return_value=Mock(ok=True, json=lambda: payload)):
        record = wikipedia.fetch_top_articles(include_metadata=True)[0]
    assert record["url"] == "https://en.wikipedia.org/wiki/Bali"
    assert record["observed_at"]
    assert "published_at" not in record
    assert "excerpt" not in record


@pytest.mark.parametrize("category", ["fitness", "lifestyle"])
def test_guardian_maps_lifestyle_categories_to_real_section(category):
    with patch.object(
        guardian.requests,
        "get",
        return_value=Mock(ok=True, json=lambda: {"response": {"results": []}}),
    ) as request:
        guardian.fetch_articles(category)
    params = request.call_args.kwargs["params"]
    assert params["section"] == "lifeandstyle"
    assert params["show-fields"] == "trailText"
    if category == "fitness":
        assert params["q"] == "fitness OR exercise"
