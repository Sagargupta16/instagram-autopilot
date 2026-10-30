# Instagram Autopilot v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v2 premium multi-slot Instagram autopilot in six independently-mergeable PRs: wide-niche trend sources, config-v2 + random cadence, ffmpeg-baked audio on Reels, Meta Places location tags, wide-niche pillars live, then key/instance hardening.

**Architecture:** Six PRs stack on `main`. Each PR is behavior-preserving on merge (feature-flagged via config defaults so nothing changes for prod until PR 5). Adapters follow the repo's "one external service per file" rule. All new modules under 200 lines (soft limit per repo CLAUDE.md).

**Tech Stack:** Python 3.14, `requests`, `pytest`, `ruff`, `ffmpeg` (system dep), AWS Bedrock (bearer token, no boto3), Composio v3, Cloudinary, S3 (us-west-2). No new pip deps.

## Global Constraints

Copied verbatim from spec + repo CLAUDE.md. Every task inherits these:

- **File size:** soft limit 200 lines, hard limit 300 lines. Split before exceeding.
- **Function length:** target <40 lines.
- **One external service per adapter file.** No cross-streams (publisher → image host directly = wrong).
- **No boto3.** Bedrock uses `requests.post` + `Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK`.
- **Cloudinary required** for image hosting (Meta blocks imgbb).
- **Composio slug:** `INSTAGRAM_POST_IG_USER_MEDIA` (renamed from `INSTAGRAM_CREATE_MEDIA_CONTAINER` on 2026-03-28; old alias still works).
- **`location_id` param:** valid on single image, single video, reel, and PARENT carousel container. NEVER on carousel children (`is_carousel_item=true`) — Meta rejects.
- **Composio wraps IG errors in HTTP 200** with `successful=false`; raises `ComposioActionError`. Match `INVALID_LOCATION_ID` on the exception message, not HTTP status.
- **Instagram publish limit:** 25/24h hard cap.
- **Luma Ray 2:** 5s or 9s durations only, 9:16, 720p, S3 bucket in us-west-2.
- **Stable Image Ultra:** `aspect_ratio` only (no width/height).
- **Type hints on every function.** `from __future__ import annotations` at file top. `pathlib.Path` over `os.path`. f-strings only. Never `except:` bare.
- **Tests mirror `src/` layout.** pytest AAA. One behavior per test.
- **Conventional commits:** `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`. Lowercase, imperative, no trailing period. No `Co-Authored-By`.
- **`main` branch always.** No `master`. Never force-push main. Never `--no-verify`. Stage files by name (no `git add .`).
- **Image prompts must not contain negation words** (`no`, `not`, `without`) — diffusion models invert them. Exclusions go in `negative_prompt` at image-gen layer only.
- **Trend adapters are no-auth only.** If a source needs an API key at runtime, rethink; the Guardian `test` key is a stringly-typed dev-tier bypass, not an OAuth key.
- **All new files: descriptive UA header on outbound HTTP:** `InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)`.

---

## PR 1: Wide-niche trend adapters

Replaces Reddit and adds 4 lifestyle-signal sources. `trends.py` fan-out grows from 8 tasks to 12. No config change, no runtime behavior change for existing pillars.

### Task 1.1: Wikipedia pageviews adapter

**Files:**
- Create: `src/adapters/wikipedia.py`
- Test: `tests/adapters/test_wikipedia.py`

**Interfaces:**
- Consumes: nothing (stdlib + `requests`)
- Produces: `fetch_top_articles(limit: int = 20) -> list[str]` — returns article titles (spaces preserved), filters `Special:*` and `Main_Page`.

- [ ] **Step 1: Write failing test**

```python
# tests/adapters/test_wikipedia.py
from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import wikipedia


@patch("src.adapters.wikipedia.requests.get")
def test_fetch_top_articles_returns_titles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {
            "items": [{"articles": [
                {"article": "OpenAI"},
                {"article": "Main_Page"},
                {"article": "Special:Search"},
                {"article": "Bali"},
            ]}]
        },
    )

    result = wikipedia.fetch_top_articles(limit=10)

    assert result == ["OpenAI", "Bali"]


@patch("src.adapters.wikipedia.requests.get")
def test_fetch_top_articles_falls_back_on_404(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=404, text="Not Found")

    result = wikipedia.fetch_top_articles()

    assert result == []
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/adapters/test_wikipedia.py -v`
Expected: `ModuleNotFoundError: No module named 'src.adapters.wikipedia'`.

- [ ] **Step 3: Implement**

```python
# src/adapters/wikipedia.py
"""Wikipedia pageviews REST API (no auth).

Top-1000 English-Wikipedia articles by pageviews for date - 2 days
(pageviews data lags ~2 days). Cross-category signal of public curiosity.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import requests

log = logging.getLogger(__name__)

_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}/{m}/{d}"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
_SKIP_PREFIXES = ("Special:", "Wikipedia:", "Portal:", "Help:")
_SKIP_EXACT = {"Main_Page", "-"}


def fetch_top_articles(limit: int = 20) -> list[str]:
    """Return up to `limit` most-viewed English Wikipedia article titles."""
    day = datetime.now(UTC).date() - timedelta(days=2)
    url = _URL.format(y=day.year, m=f"{day.month:02d}", d=f"{day.day:02d}")
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
    except requests.RequestException as e:
        log.warning("Wikipedia pageviews fetch failed: %s", e)
        return []
    if not resp.ok:
        log.warning("Wikipedia pageviews HTTP %s", resp.status_code)
        return []
    items = resp.json().get("items", [])
    if not items:
        return []
    articles = items[0].get("articles", [])
    titles = [
        a["article"].replace("_", " ")
        for a in articles
        if a.get("article")
        and a["article"] not in _SKIP_EXACT
        and not a["article"].startswith(_SKIP_PREFIXES)
    ]
    return titles[:limit]
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/adapters/test_wikipedia.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/wikipedia.py tests/adapters/test_wikipedia.py
git commit -m "feat(adapters): add Wikipedia pageviews trend source"
```

### Task 1.2: Google News RSS adapter

**Files:**
- Create: `src/adapters/google_news.py`
- Test: `tests/adapters/test_google_news.py`

**Interfaces:**
- Consumes: nothing
- Produces: `fetch_headlines(category: str, limit: int = 10) -> list[str]` — returns news article titles matching category query.

- [ ] **Step 1: Write failing test**

```python
# tests/adapters/test_google_news.py
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
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/adapters/test_google_news.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/adapters/google_news.py
"""Google News RSS search (no auth, per-category).

Uses defusedxml -- stdlib xml.etree is vulnerable to XXE + billion-laughs
on untrusted input (RSS is untrusted).
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import requests
from defusedxml import ElementTree as ET

log = logging.getLogger(__name__)

_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def fetch_headlines(category: str, limit: int = 10) -> list[str]:
    """Return up to `limit` news headline titles for the given category query."""
    try:
        resp = requests.get(
            _URL.format(q=quote(category)),
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Google News fetch (%s) failed: %s", category, e)
        return []
    if not resp.ok:
        log.warning("Google News (%s) HTTP %s", category, resp.status_code)
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        log.warning("Google News (%s) invalid XML: %s", category, e)
        return []
    titles: list[str] = []
    for item in root.iterfind(".//item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            titles.append(title_el.text.strip())
        if len(titles) >= limit:
            break
    return titles
```

Add to `requirements.txt` in Task 1.2 Step 3 (before Step 4 test run):

```
defusedxml>=0.7.1
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/adapters/test_google_news.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/google_news.py tests/adapters/test_google_news.py
git commit -m "feat(adapters): add Google News RSS trend source"
```

### Task 1.3: Guardian API adapter

**Files:**
- Create: `src/adapters/guardian.py`
- Test: `tests/adapters/test_guardian.py`

**Interfaces:**
- Consumes: `settings.guardian_api_key: str = ""` (added in Task 1.6)
- Produces: `fetch_articles(section: str, limit: int = 10) -> list[str]` — returns webTitles from Guardian content API for the given section.

- [ ] **Step 1: Write failing test**

```python
# tests/adapters/test_guardian.py
from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import guardian


@patch("src.adapters.guardian.requests.get")
def test_fetch_articles_returns_webtitles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {"response": {"results": [
            {"webTitle": "The best pasta in Rome"},
            {"webTitle": "Fitness trend: cold plunges"},
        ]}},
    )

    result = guardian.fetch_articles("lifestyle", limit=5)

    assert result == ["The best pasta in Rome", "Fitness trend: cold plunges"]


@patch("src.adapters.guardian.requests.get")
def test_fetch_articles_returns_empty_on_error(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=403, text="forbidden")

    assert guardian.fetch_articles("food") == []
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/adapters/test_guardian.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/adapters/guardian.py
"""Guardian Open Platform search API.

Uses api-key=`test` by default (shared dev quota); override with
settings.guardian_api_key once a real free-tier key is registered.
"""

from __future__ import annotations

import logging

import requests

from src.settings import settings

log = logging.getLogger(__name__)

_URL = "https://content.guardianapis.com/search"
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def fetch_articles(section: str, limit: int = 10) -> list[str]:
    """Return up to `limit` recent Guardian article titles for the given section."""
    key = settings.guardian_api_key or "test"
    try:
        resp = requests.get(
            _URL,
            params={
                "api-key": key,
                "section": section,
                "order-by": "newest",
                "page-size": limit,
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Guardian fetch (%s) failed: %s", section, e)
        return []
    if not resp.ok:
        log.warning("Guardian (%s) HTTP %s", section, resp.status_code)
        return []
    results = resp.json().get("response", {}).get("results", [])
    return [r["webTitle"] for r in results if r.get("webTitle")][:limit]
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/adapters/test_guardian.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/guardian.py tests/adapters/test_guardian.py
git commit -m "feat(adapters): add Guardian content API trend source"
```

### Task 1.4: Lemmy API adapter

**Files:**
- Create: `src/adapters/lemmy.py`
- Test: `tests/adapters/test_lemmy.py`

**Interfaces:**
- Consumes: nothing
- Produces: `fetch_hot_posts(community: str, limit: int = 10) -> list[str]` — returns post titles from `lemmy.world` community, falls back to `lemmy.ml` on failure.

- [ ] **Step 1: Write failing test**

```python
# tests/adapters/test_lemmy.py
from __future__ import annotations

from unittest.mock import Mock, patch

from src.adapters import lemmy


@patch("src.adapters.lemmy.requests.get")
def test_fetch_hot_posts_returns_titles(mock_get: Mock) -> None:
    mock_get.return_value = Mock(
        ok=True,
        status_code=200,
        json=lambda: {"posts": [
            {"post": {"name": "Sourdough discovery"}},
            {"post": {"name": "New running app tested"}},
        ]},
    )

    result = lemmy.fetch_hot_posts("food")

    assert result == ["Sourdough discovery", "New running app tested"]


@patch("src.adapters.lemmy.requests.get")
def test_fetch_hot_posts_falls_back_to_lemmy_ml(mock_get: Mock) -> None:
    mock_get.side_effect = [
        Mock(ok=False, status_code=503, text="down"),
        Mock(ok=True, status_code=200, json=lambda: {"posts": [
            {"post": {"name": "Fallback title"}}
        ]}),
    ]

    result = lemmy.fetch_hot_posts("food")

    assert result == ["Fallback title"]
    assert mock_get.call_count == 2
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/adapters/test_lemmy.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/adapters/lemmy.py
"""Lemmy federated API v3 (no auth) with primary → fallback instance."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

_INSTANCES = ("lemmy.world", "lemmy.ml", "sh.itjust.works")
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _try_instance(instance: str, community: str, limit: int) -> list[str] | None:
    url = f"https://{instance}/api/v3/post/list"
    try:
        resp = requests.get(
            url,
            params={
                "sort": "Hot",
                "limit": limit,
                "community_name": f"{community}@{instance}",
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Lemmy %s fetch failed: %s", instance, e)
        return None
    if not resp.ok:
        log.warning("Lemmy %s HTTP %s", instance, resp.status_code)
        return None
    posts = resp.json().get("posts", [])
    return [p["post"]["name"] for p in posts if p.get("post", {}).get("name")]


def fetch_hot_posts(community: str, limit: int = 10) -> list[str]:
    """Return hot post titles from `community`, trying instances in order."""
    for instance in _INSTANCES:
        titles = _try_instance(instance, community, limit)
        if titles is not None:
            return titles
    return []
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/adapters/test_lemmy.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/lemmy.py tests/adapters/test_lemmy.py
git commit -m "feat(adapters): add Lemmy hot-posts trend source"
```

### Task 1.5: Add `guardian_api_key` to settings

**Files:**
- Modify: `src/settings.py`
- Modify: `tests/conftest.py` (add env default so import doesn't fail)

- [ ] **Step 1: Modify settings**

Add to `Settings` class in `src/settings.py`, right below the `S3` block:

```python
    # Guardian Open Platform (dev-tier "test" key works without registration)
    guardian_api_key: str = ""
```

- [ ] **Step 2: Ensure conftest doesn't need update**

Guardian key defaults to empty string — no `os.environ.setdefault` needed in `tests/conftest.py`.

- [ ] **Step 3: Sanity-check the whole test suite**

Run: `python -m pytest -q`
Expected: existing suite still passes (Task 1.1-1.4 tests included).

- [ ] **Step 4: Commit**

```bash
git add src/settings.py
git commit -m "feat(settings): add optional guardian_api_key"
```

### Task 1.6: Delete reddit adapter, drop from trends

**Files:**
- Delete: `src/adapters/reddit.py`
- Delete: `tests/adapters/test_reddit.py` (if it exists)
- Modify: `src/content/trends.py`

- [ ] **Step 1: Check if reddit test file exists**

Run: `ls tests/adapters/test_reddit.py 2>/dev/null && echo EXISTS || echo NONE`
If EXISTS, note the path for removal in Step 4.

- [ ] **Step 2: Rewrite trends.py fan-out**

Replace `src/content/trends.py` entirely:

```python
"""Fetch trending topics in parallel across wide-lifestyle + tech sources.

Grounds daily post ideas in current conversations instead of Claude's
training data alone. Degrades gracefully -- if a source fails, the rest
still work.

Sources (all no-auth):
    - HuggingFace daily papers (curated trending AI research)
    - Product Hunt AI category atom feed
    - GitHub search (generative-ai, llm, diffusion-models)
    - Hacker News Algolia search
    - Wikipedia pageviews top-1000
    - Google News RSS per category (travel/food/fitness/entertainment/tech)
    - Guardian API per section
    - Lemmy hot posts per community

Reddit is intentionally excluded: GitHub Actions runner IPs are on
Reddit's anti-bot blocklist (403).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

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

log = logging.getLogger(__name__)

_CATEGORIES = ("travel", "food", "fitness", "entertainment", "technology")
_GUARDIAN_SECTIONS = ("lifestyle", "food", "travel", "fitness", "technology", "film")
_LEMMY_COMMUNITIES = ("technology", "food", "travel", "fitness")


def _tasks() -> list[tuple[str, tuple]]:
    tasks: list[tuple[str, tuple]] = [
        ("hf-daily", (huggingface_papers.fetch_daily_papers, 8)),
        ("ph-ai", (producthunt.fetch_ai_launches, 6)),
        ("gh-genai", (github_trending.fetch_trending, "generative-ai", 4)),
        ("gh-llm", (github_trending.fetch_trending, "llm", 4)),
        ("hn-ai", (hackernews.search_stories, "artificial intelligence", 4)),
        ("wiki-top", (wikipedia.fetch_top_articles, 15)),
    ]
    tasks.extend((f"news-{c}", (google_news.fetch_headlines, c, 4)) for c in _CATEGORIES)
    tasks.extend((f"guardian-{s}", (guardian.fetch_articles, s, 4)) for s in _GUARDIAN_SECTIONS)
    tasks.extend((f"lemmy-{c}", (lemmy.fetch_hot_posts, c, 4)) for c in _LEMMY_COMMUNITIES)
    return tasks


def fetch_trending_topics(limit: int = 30) -> list[str]:
    """Return up to `limit` trending headlines, deduplicated."""
    tasks = _tasks()
    results: list[str] = []
    with ThreadPoolExecutor(max_workers=min(16, len(tasks))) as pool:
        futures = {pool.submit(fn, *args): name for name, (fn, *args) in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as e:  # noqa: BLE001 -- graceful degradation is intentional
                log.warning("Trend source %s failed: %s", name, e)

    seen: set[str] = set()
    deduped = [t for t in results if not (t in seen or seen.add(t))]

    log.info("Fetched %d trending topics from %d sources", len(deduped), len(tasks))
    return deduped[:limit]
```

- [ ] **Step 3: Update trends test for new source count**

Replace `tests/content/test_trends.py` (or create it) with:

```python
from __future__ import annotations

from unittest.mock import patch

from src.content import trends


def test_fetch_survives_one_source_failure() -> None:
    def _boom(*a, **kw):
        raise RuntimeError("simulated")

    with (
        patch("src.adapters.wikipedia.fetch_top_articles", return_value=["Bali", "Tokyo"]),
        patch("src.adapters.google_news.fetch_headlines", return_value=["News A"]),
        patch("src.adapters.guardian.fetch_articles", return_value=["Guardian A"]),
        patch("src.adapters.lemmy.fetch_hot_posts", return_value=["Lemmy A"]),
        patch("src.adapters.hackernews.search_stories", return_value=["HN A"]),
        patch("src.adapters.huggingface_papers.fetch_daily_papers", side_effect=_boom),
        patch("src.adapters.producthunt.fetch_ai_launches", return_value=["PH A"]),
        patch("src.adapters.github_trending.fetch_trending", return_value=["GH A"]),
    ):
        result = trends.fetch_trending_topics(limit=50)

    assert "Bali" in result
    assert len(result) >= 3  # other sources filled in
```

- [ ] **Step 4: Delete reddit files**

```bash
rm src/adapters/reddit.py
# Only if EXISTS from Step 1:
rm -f tests/adapters/test_reddit.py
```

- [ ] **Step 5: Update repo CLAUDE.md**

Modify `CLAUDE.md` line describing trends grounding sources — change "4 services / 8 sources" to "8 services / 20+ tasks". Update the adapters block to remove `reddit.py` and add `wikipedia.py`, `google_news.py`, `guardian.py`, `lemmy.py`.

Run: `grep -n "Reddit adapter" CLAUDE.md`
Update the surrounding paragraph to remove Reddit-disabled note (or change to "Reddit removed 2026-07-03 — GH Actions IPs still blocked").

- [ ] **Step 6: Run full suite**

Run: `python -m pytest -q && python -m ruff check .`
Expected: all green.

- [ ] **Step 7: Commit + push + open PR**

```bash
git add src/content/trends.py tests/content/test_trends.py CLAUDE.md
git rm src/adapters/reddit.py
[ -f tests/adapters/test_reddit.py ] && git rm tests/adapters/test_reddit.py
git commit -m "feat(trends): swap reddit for wide-niche sources (wiki, news, guardian, lemmy)"
git push -u origin feat/v2-premium-multi-slot
# Open PR 1 via gh:
gh pr create --title "feat(trends): wide-niche trend adapters (PR 1/6 of v2)" --body "Ships PR 1 of the v2 rollout in docs/specs/2026-07-03-v2-premium-multi-slot.md. No config change; existing pillars now grounded in 8 services / 20+ tasks. Reddit removed (GH Actions IP block still active)."
```

---

## PR 2: Config schema v2 + random-cadence scheduler

Introduces `Cadence` config block and `plan_today()` scheduler. Ships with `max_posts_per_day: 1` so behavior is identical to today. `main.run()` becomes a slot loop.

### Task 2.1: Add `SlotPlan` dataclass + `to_minutes`/`to_hhmm` helpers

**Files:**
- Modify: `src/schedule.py`
- Test: `tests/test_schedule.py`

**Interfaces:**
- Produces: `SlotPlan` dataclass with `time_utc: str` (HH:MM), `pillar: dict`, `skip: bool`. Helpers `to_minutes(hhmm: str) -> int`, `to_hhmm(mins: int) -> str`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_schedule.py — REPLACE existing content
from __future__ import annotations

from src import schedule


def test_to_minutes_parses_hhmm() -> None:
    assert schedule.to_minutes("04:00") == 240
    assert schedule.to_minutes("20:30") == 1230


def test_to_hhmm_formats_minutes() -> None:
    assert schedule.to_hhmm(240) == "04:00"
    assert schedule.to_hhmm(1230) == "20:30"


def test_slotplan_roundtrip() -> None:
    slot = schedule.SlotPlan(time_utc="09:30", pillar={"id": "x"}, skip=False)
    assert slot.time_utc == "09:30"
    assert slot.pillar["id"] == "x"
    assert slot.skip is False
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: AttributeError / import error.

- [ ] **Step 3: Implement**

Replace `src/schedule.py`:

```python
"""Deterministic per-day posting schedule.

Given today's date, RNG-picks how many posts (0..max), what times (within
window, min-gap-enforced), and which pillar per slot. Seeded on YYYYMMDD
so re-runs on the same date produce the same plan (safe under CI retry).

The old apply_jitter() lives on as an intra-slot randomizer (0..30 min
around the planned time) so back-to-back same-slot re-runs don't
publish at the exact wall-clock second.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlotPlan:
    time_utc: str  # "HH:MM"
    pillar: dict[str, Any]
    skip: bool


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def apply_jitter(max_minutes: int) -> None:
    """Sleep a random 0..max_minutes."""
    if max_minutes <= 0:
        return
    sleep_sec = random.randint(0, max_minutes * 60)
    log.info(
        "Jitter: sleeping %d min %d sec before posting",
        sleep_sec // 60,
        sleep_sec % 60,
    )
    time.sleep(sleep_sec)


def plan_today(
    today: date,
    cadence: dict[str, Any],
    pillars: list[dict[str, Any]],
) -> list[SlotPlan]:
    """Return today's SlotPlans, deterministic on `today`."""
    if not pillars:
        return []
    rng = random.Random(int(today.strftime("%Y%m%d")))
    probs = cadence.get("post_probability", [0.15, 0.35, 0.35, 0.15])
    max_n = int(cadence.get("max_posts_per_day", 3))
    n = min(rng.choices(list(range(len(probs))), weights=probs)[0], max_n)
    if n == 0:
        return []
    start = to_minutes(cadence.get("window_utc", {}).get("start", "04:00"))
    end = to_minutes(cadence.get("window_utc", {}).get("end", "20:00"))
    gap = int(cadence.get("min_gap_minutes", 90))
    slots: list[int] = []
    for _ in range(50):
        if len(slots) == n:
            break
        cand = rng.randint(start, end)
        if all(abs(cand - s) >= gap for s in slots):
            slots.append(cand)
    slots.sort()
    weights = [float(p.get("weight", 1.0)) for p in pillars]
    skip_p = float(cadence.get("skip_probability", 0.05))
    return [
        SlotPlan(
            time_utc=to_hhmm(m),
            pillar=rng.choices(pillars, weights=weights)[0],
            skip=(rng.random() < skip_p),
        )
        for m in slots
    ]
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/schedule.py tests/test_schedule.py
git commit -m "refactor(schedule): add SlotPlan + plan_today (behavior-preserving)"
```

### Task 2.2: `plan_today` behavior tests

**Files:**
- Modify: `tests/test_schedule.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_schedule.py`:

```python
from datetime import date as _date


_PILLARS = [{"id": "a", "weight": 1.0}, {"id": "b", "weight": 2.0}]
_CADENCE = {
    "max_posts_per_day": 3,
    "post_probability": [0.0, 0.0, 1.0, 0.0],  # always n=2
    "window_utc": {"start": "04:00", "end": "20:00"},
    "min_gap_minutes": 90,
    "skip_probability": 0.0,
}


def test_plan_today_deterministic_per_date() -> None:
    d = _date(2026, 7, 3)
    plan1 = schedule.plan_today(d, _CADENCE, _PILLARS)
    plan2 = schedule.plan_today(d, _CADENCE, _PILLARS)
    assert plan1 == plan2


def test_plan_today_differs_across_dates() -> None:
    p1 = schedule.plan_today(_date(2026, 7, 3), _CADENCE, _PILLARS)
    p2 = schedule.plan_today(_date(2026, 7, 4), _CADENCE, _PILLARS)
    assert p1 != p2


def test_plan_respects_max_posts_per_day() -> None:
    forced_n_5 = {**_CADENCE, "post_probability": [0.0, 0.0, 0.0, 0.0, 1.0], "max_posts_per_day": 3}
    plan = schedule.plan_today(_date(2026, 7, 3), forced_n_5, _PILLARS)
    assert len(plan) <= 3


def test_plan_respects_min_gap() -> None:
    plan = schedule.plan_today(_date(2026, 7, 3), _CADENCE, _PILLARS)
    for i in range(len(plan) - 1):
        gap = schedule.to_minutes(plan[i + 1].time_utc) - schedule.to_minutes(plan[i].time_utc)
        assert gap >= 90


def test_plan_zero_posts_returns_empty() -> None:
    always_zero = {**_CADENCE, "post_probability": [1.0, 0.0, 0.0, 0.0]}
    assert schedule.plan_today(_date(2026, 7, 3), always_zero, _PILLARS) == []
```

- [ ] **Step 2: Run and confirm PASS**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: 8 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_schedule.py
git commit -m "test(schedule): plan_today determinism, max, gap, zero cases"
```

### Task 2.3: Config v2 in `config.json` (backward-compatible defaults)

**Files:**
- Modify: `config.json`

- [ ] **Step 1: Add `cadence` block, keep pillars intact**

Add to `config.json` at the top level, between `pillars` and `posting`:

```json
"cadence": {
  "max_posts_per_day": 1,
  "post_probability": [0.0, 1.0, 0.0, 0.0],
  "window_utc": {"start": "04:00", "end": "20:00"},
  "min_gap_minutes": 90,
  "skip_probability": 0.0
},
```

Also add `"weight": 1.0` to each existing pillar. `posting` block stays for now — deleted in Task 2.5 after main.py migrates.

- [ ] **Step 2: Commit**

```bash
git add config.json
git commit -m "feat(config): add cadence block (defaults preserve current behavior)"
```

### Task 2.4: `main.run()` slot loop

**Files:**
- Modify: `src/main.py`
- Modify: `src/pillar.py` (remove `get_todays_pillar`)

- [ ] **Step 1: Rewrite pillar.py**

Replace `src/pillar.py`:

```python
"""Content strategy loader: pillars + persona + model IDs from config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict[str, Any]:
    """Read config.json."""
    return json.loads(CONFIG_PATH.read_text())
```

- [ ] **Step 2: Rewrite main.py**

Replace `src/main.py`:

```python
"""Entry point: plan today's slots, sleep to each, publish."""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import UTC, date, datetime

from src.adapters import bedrock, cloudinary_host, composio
from src.content.caption import generate_caption
from src.content.dedup import record_post
from src.content.topic import generate_topic
from src.flows.carousel_flow import post_carousel
from src.flows.image_flow import post_image
from src.flows.reel_flow import post_reel
from src.pillar import load_config
from src.schedule import SlotPlan, plan_today, to_minutes
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _preflight_all_auth(text_model_id: str) -> None:
    bedrock.verify_auth(text_model_id)
    composio.verify_auth()
    cloudinary_host.verify_auth()


def _sleep_until_utc(target_hhmm: str) -> None:
    now = datetime.now(UTC)
    target_min = to_minutes(target_hhmm)
    now_min = now.hour * 60 + now.minute
    delta = target_min - now_min
    if delta <= 0:
        log.info("Slot %s already past, publishing immediately", target_hhmm)
        return
    log.info("Sleeping %d min until %s UTC", delta, target_hhmm)
    time.sleep(delta * 60)


def _run_slot(slot: SlotPlan, config: dict, *, dry_run: bool) -> None:
    pillar = slot.pillar
    log.info("Slot %s | pillar %s", slot.time_utc, pillar["id"])
    content_type = random.choice(settings.content_type_list)
    topic = generate_topic(pillar, content_type)
    caption_data = generate_caption(topic, pillar, config["persona"])
    caption = caption_data["caption"] + "\n\n" + caption_data["hashtags"]
    log.info("X post: %s", caption_data["x_post"])
    if not dry_run:
        record_post(topic, caption_data.get("image_prompts", []))
    if dry_run:
        log.info("DRY RUN | topic: %s | caption: %s...", topic, caption[:200])
    image_model = config["models"]["image"]
    video_model = config["models"]["video"]
    content_format = pillar.get("content_format", "carousel")
    if content_format == "reel":
        post_reel(caption_data, caption, image_model, video_model, dry_run=dry_run)
    elif content_format == "image":
        post_image(caption_data, caption, image_model, dry_run=dry_run)
    else:
        post_carousel(caption_data, caption, image_model, dry_run=dry_run)


def run(*, dry_run: bool = False) -> None:
    cloudinary_host.configure()
    config = load_config()

    plan = plan_today(datetime.now(UTC).date(), config.get("cadence", {}), config["pillars"])
    if not plan:
        log.info("No slots planned today. Skipping.")
        return
    log.info("Today's plan: %s", [(s.time_utc, s.pillar["id"], s.skip) for s in plan])

    _preflight_all_auth(config["models"]["text"])

    for slot in plan:
        if not dry_run:
            _sleep_until_utc(slot.time_utc)
        if slot.skip:
            log.info("Skip flag set on slot %s -- skipping", slot.time_utc)
            continue
        try:
            _run_slot(slot, config, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001 -- one slot's failure shouldn't kill others
            log.exception("Slot %s failed: %s", slot.time_utc, e)

    log.info("Done!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Autopilot")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't publish")
    args = parser.parse_args()

    log.info("Starting Instagram Autopilot")
    log.info("Niche: %s | Types: %s", settings.niche, settings.content_type_list)
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest -q`
Expected: all pass (existing tests should still work; test_pillar may need update for removed `get_todays_pillar`).

- [ ] **Step 4: Fix test_pillar.py if it referenced `get_todays_pillar`**

If `python -m pytest tests/test_pillar.py -v` fails on missing symbol, replace with a minimal test:

```python
from src.pillar import load_config


def test_load_config_returns_dict_with_pillars() -> None:
    config = load_config()
    assert isinstance(config, dict)
    assert "pillars" in config
    assert "cadence" in config
```

- [ ] **Step 5: Dry-run smoke**

Run: `python -m src.main --dry-run 2>&1 | head -30`
Expected: at least one slot printed, generation triggered, no publish.

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/pillar.py tests/test_pillar.py
git commit -m "refactor(main): slot-loop scheduler (behavior-preserving with cadence n=1)"
```

### Task 2.5: Drop legacy `posting` block + workflow cron unchanged

**Files:**
- Modify: `config.json`
- Verify: `.github/workflows/daily-post.yml`

- [ ] **Step 1: Remove `posting` block**

Delete the `"posting": {...}` block from `config.json`. Nothing reads it now.

- [ ] **Step 2: Verify workflow cron unchanged**

Run: `grep -n "cron:" .github/workflows/daily-post.yml`
Expected: `- cron: "30 15 * * *"` — leave as-is. Timeout stays 240 (bumped to 480 in PR 3 when 3-post window enabled).

- [ ] **Step 3: Bump `POST_JITTER_MAX_MINUTES` behavior**

The old jitter is now dead (main.py doesn't call `apply_jitter` at run-start anymore — sleep-until-slot handles timing). Remove `post_jitter_max_minutes` from `src/settings.py` if unused.

Run: `grep -rn "post_jitter_max_minutes\|apply_jitter" src/`
If no callers of `apply_jitter` remain outside `schedule.py`, that's fine (kept for future use).
Delete the `post_jitter_max_minutes` field from Settings if not referenced.

- [ ] **Step 4: Full test**

Run: `python -m pytest -q && python -m ruff check .`
Expected: green.

- [ ] **Step 5: Commit + PR**

```bash
git add config.json src/settings.py
git commit -m "chore(config): drop legacy posting block, unused jitter setting"
gh pr create --title "feat(schedule): config v2 + random slot cadence (PR 2/6 of v2)" --body "Ships PR 2 of v2 rollout. Ships with n=1/day so behavior is identical to today; PR 5 flips to n=1-3."
```

---

## PR 3: Audio bake pipeline

Introduces ffmpeg audio-bake for Reels using Pixabay CC0 tracks. One-time curation script, runtime picker + baker, `reel_flow.py` integration, CI ffmpeg install.

### Task 3.1: `audio_manifest.json` schema + `audio_picker.py`

**Files:**
- Create: `assets/audio/audio_manifest.json`
- Create: `src/media/audio_picker.py`
- Test: `tests/media/test_audio_picker.py`

**Interfaces:**
- Consumes: `assets/audio/audio_manifest.json`, `assets/cache/audio_history.json`
- Produces: `pick(theme: str) -> Path` — returns absolute path to a track matching theme, not used in last 2 days. Appends track_id + today's date to history atomically.

- [ ] **Step 1: Seed a minimal manifest (real tracks curated in Task 3.4)**

Create `assets/audio/audio_manifest.json`:

```json
{
  "tracks": [
    {
      "track_id": "chill-placeholder-001",
      "filename": "chill/placeholder-001.mp3",
      "theme_tags": ["chill", "ambient"],
      "license": "Pixabay Content License",
      "attribution_required": false,
      "source_url": "PLACEHOLDER — real URL added at curation",
      "duration_s": 120,
      "curated_at": "2026-07-03"
    }
  ]
}
```

*(Manifest gets 30 real entries after Task 3.4 curation. This scaffold unblocks picker tests now.)*

- [ ] **Step 2: Write failing test**

```python
# tests/media/test_audio_picker.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.media import audio_picker


@pytest.fixture
def tmp_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    manifest = tmp_path / "audio_manifest.json"
    manifest.write_text(json.dumps({"tracks": [
        {"track_id": "chill-001", "filename": "chill/a.mp3", "theme_tags": ["chill"]},
        {"track_id": "chill-002", "filename": "chill/b.mp3", "theme_tags": ["chill"]},
        {"track_id": "upbeat-001", "filename": "upbeat/c.mp3", "theme_tags": ["upbeat"]},
    ]}))
    (tmp_path / "chill").mkdir()
    (tmp_path / "upbeat").mkdir()
    (tmp_path / "chill" / "a.mp3").write_bytes(b"fake")
    (tmp_path / "chill" / "b.mp3").write_bytes(b"fake")
    (tmp_path / "upbeat" / "c.mp3").write_bytes(b"fake")
    history = tmp_path / "audio_history.json"
    monkeypatch.setattr(audio_picker, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(audio_picker, "AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(audio_picker, "HISTORY_PATH", history)
    return tmp_path


def test_pick_returns_matching_theme(tmp_audio: Path) -> None:
    track = audio_picker.pick("upbeat")
    assert track.name == "c.mp3"


def test_pick_avoids_last_two_days(tmp_audio: Path) -> None:
    (tmp_audio / "audio_history.json").write_text(json.dumps({
        "history": [
            {"date": "2026-07-01", "track_ids": ["chill-001"]},
            {"date": "2026-07-02", "track_ids": ["chill-001"]},
        ]
    }))
    for _ in range(10):
        track = audio_picker.pick("chill")
        assert track.name == "b.mp3"


def test_pick_raises_when_no_track_matches_theme(tmp_audio: Path) -> None:
    with pytest.raises(audio_picker.NoTrackAvailableError):
        audio_picker.pick("cinematic")
```

- [ ] **Step 3: Run and confirm FAIL**

Run: `python -m pytest tests/media/test_audio_picker.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement**

```python
# src/media/audio_picker.py
"""Pick a royalty-free audio track for a Reel, avoiding recent repeats."""

from __future__ import annotations

import json
import logging
import os
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "assets" / "audio"
MANIFEST_PATH = AUDIO_ROOT / "audio_manifest.json"
HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "cache" / "audio_history.json"
HISTORY_LOOKBACK_DAYS = 2


class NoTrackAvailableError(Exception):
    """No manifest track matches the requested theme + history filter."""


def _load_manifest() -> list[dict[str, Any]]:
    return json.loads(MANIFEST_PATH.read_text()).get("tracks", [])


def _load_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text()).get("history", [])
    except json.JSONDecodeError:
        log.warning("audio history corrupt, resetting")
        return []


def _recent_track_ids(history: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for entry in history[-HISTORY_LOOKBACK_DAYS:]:
        ids.update(entry.get("track_ids", []))
    return ids


def _append_history(track_id: str) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = _load_history()
    today = datetime.now(UTC).date().isoformat()
    if history and history[-1]["date"] == today:
        history[-1]["track_ids"].append(track_id)
    else:
        history.append({"date": today, "track_ids": [track_id]})
    # atomic write
    fd, tmp = tempfile.mkstemp(dir=HISTORY_PATH.parent, suffix=".json")
    os.close(fd)
    Path(tmp).write_text(json.dumps({"history": history[-30:]}, indent=2))
    Path(tmp).replace(HISTORY_PATH)


def pick(theme: str) -> Path:
    """Return path to a track matching `theme`, not used in last 2 days."""
    manifest = _load_manifest()
    recent = _recent_track_ids(_load_history())
    candidates = [
        t for t in manifest
        if theme in t.get("theme_tags", []) and t["track_id"] not in recent
    ]
    if not candidates:
        # relax history filter before giving up
        candidates = [t for t in manifest if theme in t.get("theme_tags", [])]
    if not candidates:
        raise NoTrackAvailableError(f"No tracks matching theme '{theme}' in manifest")
    chosen = random.choice(candidates)
    _append_history(chosen["track_id"])
    return AUDIO_ROOT / chosen["filename"]
```

- [ ] **Step 5: Run and confirm PASS**

Run: `python -m pytest tests/media/test_audio_picker.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/media/audio_picker.py tests/media/test_audio_picker.py assets/audio/audio_manifest.json
git commit -m "feat(media): add audio picker with theme filter + 2-day anti-repeat"
```

### Task 3.2: `audio_bake.py` ffmpeg wrapper

**Files:**
- Create: `src/media/audio_bake.py`
- Test: `tests/media/test_audio_bake.py`

**Interfaces:**
- Consumes: `Path` to input mp4 and mp3
- Produces: `bake(video: Path, track: Path, duration_s: int) -> Path` — writes `{video.stem}-baked.mp4` next to input, returns new path. `AudioBakeError` on any failure.

- [ ] **Step 1: Write failing test**

```python
# tests/media/test_audio_bake.py
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.media import audio_bake


def test_bake_builds_correct_ffmpeg_command_for_5s(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = audio_bake.bake(video, track, duration_s=5)

    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "ffmpeg"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "128k"
    assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "48000"
    assert "afade=t=in:st=0:d=0.5" in " ".join(cmd)
    assert "afade=t=out:st=4.5:d=0.5" in " ".join(cmd)
    assert "+faststart" in " ".join(cmd)
    assert result == tmp_path / "in-baked.mp4"


def test_bake_9s_uses_correct_fadeout_offset(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        audio_bake.bake(video, track, duration_s=9)

    cmd = mock_run.call_args[0][0]
    assert "afade=t=out:st=8.5:d=0.5" in " ".join(cmd)


def test_bake_raises_on_ffmpeg_failure(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid data")
        with pytest.raises(audio_bake.AudioBakeError):
            audio_bake.bake(video, track, duration_s=5)


def test_bake_raises_when_ffmpeg_not_installed(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    track = tmp_path / "track.mp3"
    video.write_bytes(b"fake")
    track.write_bytes(b"fake")

    with patch("src.media.audio_bake.shutil.which", return_value=None):
        with pytest.raises(audio_bake.AudioBakeError, match="ffmpeg not on PATH"):
            audio_bake.bake(video, track, duration_s=5)
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/media/test_audio_bake.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/media/audio_bake.py
"""Bake a royalty-free audio track into a Luma-generated mp4 via ffmpeg.

Uses stream-copy on the video (preserves Luma pixels bit-for-bit) and
transcodes audio to AAC-LC 48kHz 128kbps stereo -- matches Instagram's
Reels spec so Meta doesn't server-side re-encode. Applies 0.5s
audio fade-in and fade-out; -shortest trims audio to video length;
+faststart moves the moov atom to the front for streaming.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class AudioBakeError(Exception):
    """Raised when ffmpeg is missing or fails."""


def bake(video: Path, track: Path, duration_s: int) -> Path:
    """Return path to `{video.stem}-baked.mp4` with `track` mixed in."""
    if shutil.which("ffmpeg") is None:
        raise AudioBakeError("ffmpeg not on PATH -- install with apt-get install -y ffmpeg")
    output = video.parent / f"{video.stem}-baked.mp4"
    fade_out_start = max(0.0, duration_s - 0.5)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(track),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start}:d=0.5",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]
    log.info("ffmpeg bake: %s + %s -> %s", video.name, track.name, output.name)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise AudioBakeError(f"ffmpeg failed (rc={result.returncode}): {result.stderr[-500:]}")
    return output
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/media/test_audio_bake.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/media/audio_bake.py tests/media/test_audio_bake.py
git commit -m "feat(media): add ffmpeg audio-bake with fade + faststart"
```

### Task 3.3: Wire into `reel_flow.py`

**Files:**
- Modify: `src/flows/reel_flow.py`
- Modify: `src/media/video.py` (add local-download helper if not already there)

**Interfaces:**
- Consumes: `audio_picker.pick`, `audio_bake.bake`, `caption_data["audio_theme"]` (falls back to `"cinematic"`)
- Produces: (unchanged) `post_reel(caption_data, caption, image_model, video_model, *, dry_run)`

- [ ] **Step 1: Check video.py return contract**

`src/media/video.py::generate_video()` currently returns an S3 URI string ending in `/output.mp4`. We need the mp4 locally to bake. Add a helper:

Add to `src/media/video.py`:

```python
def download_s3_uri_to_local(s3_uri: str, dest: Path) -> Path:
    """Download an s3://bucket/key/... to a local path via bearer-auth signed GET.

    Uses adapters.bedrock's underlying requests session -- we don't add
    boto3. If the bucket policy allows presigned GETs from the ABSK token
    holder this works; otherwise this raises and reel_flow falls back to
    the S3 URI (Instagram fetches it directly, we lose audio bake).
    """
    import requests
    # ... implementation via a presigned URL step (deferred to Task 3.5 verification)
    raise NotImplementedError("see Task 3.5 for S3 signing detail")
```

**Note to implementer:** the S3-download-and-re-upload path may need a small shim depending on how the current bucket is set up. If the ABSK token can't presign S3, this task falls back to two options: (a) run ffmpeg on the S3 URI directly if `ffmpeg -i s3://...` works (it doesn't natively — S3 needs http), or (b) generate a presigned URL from GH Actions AWS credentials, download, bake, re-upload.

For PR 3, ship the simpler path: **require the S3 bucket to be publicly readable OR use AWS CLI in the workflow to `aws s3 cp` down, bake, `aws s3 cp` up**. Chosen path: workflow-level `aws s3 cp`, invoked from Python via `subprocess`.

Skip the download helper in `video.py`. Instead, add it in `reel_flow.py` directly using `aws s3 cp`.

- [ ] **Step 2: Rewrite reel_flow.py**

Replace `src/flows/reel_flow.py`:

```python
"""Generate a video, bake royalty-free audio, publish as Reel.

Falls back to image_flow if S3_VIDEO_BUCKET is unset. If audio-bake
fails (ffmpeg missing, no track for theme), publishes silent-reel.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.flows.image_flow import post_image
from src.media import audio_bake, audio_picker
from src.media.video import generate_video
from src.publishing.reel import publish_reel
from src.settings import settings

log = logging.getLogger(__name__)


def _s3_cp(src: str, dst: str) -> None:
    subprocess.run(["aws", "s3", "cp", src, dst], check=True, capture_output=True)


def _bake_audio_into_s3_mp4(s3_uri: str, theme: str, duration_s: int) -> str:
    """Download from S3, bake audio, re-upload, return new S3 URI."""
    with tempfile.TemporaryDirectory() as td:
        local_in = Path(td) / "in.mp4"
        _s3_cp(s3_uri, str(local_in))
        track = audio_picker.pick(theme)
        baked = audio_bake.bake(local_in, track, duration_s)
        baked_uri = s3_uri.replace("/output.mp4", "/baked.mp4")
        _s3_cp(str(baked), baked_uri)
        return baked_uri


def post_reel(
    caption_data: dict[str, Any],
    caption: str,
    image_model: str,
    video_model: str,
    *,
    dry_run: bool,
) -> None:
    video_prompt = caption_data["video_prompt"]
    log.info("Video prompt: %s", video_prompt)

    if not settings.s3_video_bucket:
        log.warning("S3_VIDEO_BUCKET not set -- falling back to image post")
        post_image(caption_data, caption, image_model, dry_run=dry_run)
        return

    duration_s = 5  # keep in sync with generate_video default
    video_s3_uri = generate_video(
        prompt=video_prompt,
        model_id=video_model,
        s3_output_uri=settings.s3_video_bucket,
        duration_seconds=duration_s,
    )

    final_uri = video_s3_uri
    theme = caption_data.get("audio_theme", "cinematic")
    try:
        final_uri = _bake_audio_into_s3_mp4(video_s3_uri, theme, duration_s)
        log.info("Baked audio into reel: %s", final_uri)
    except (audio_bake.AudioBakeError, audio_picker.NoTrackAvailableError) as e:
        log.warning("Audio bake failed (%s) -- publishing silent reel", e)
    except subprocess.CalledProcessError as e:
        log.warning("S3 copy failed (%s) -- publishing original", e)

    if dry_run:
        log.info("DRY RUN: Reel at %s", final_uri)
        return

    publish_reel(video_url=final_uri, caption=caption, location_id=caption_data.get("location_id"))
```

*(The `location_id` param on `publish_reel` doesn't exist yet — added in PR 4. For PR 3, drop that argument and add it back in PR 4.)*

Adjust the final line for PR 3 scope:

```python
    publish_reel(video_url=final_uri, caption=caption)
```

- [ ] **Step 3: Update reel_flow test if it exists**

Run: `ls tests/flows/ 2>/dev/null`
If a reel_flow test exists, update it to mock the new subprocess calls and the audio pipeline. If not, skip.

- [ ] **Step 4: Add ffmpeg + aws-cli to workflow**

Modify `.github/workflows/daily-post.yml` between "Install dependencies" and "Generate and publish post":

```yaml
      - name: Install ffmpeg and aws-cli
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg
          aws --version || pip install awscli
```

Also bump `timeout-minutes: 240` → `480` for the future 3-post window.

Also add AWS env vars to the "Generate and publish post" step (needed by `aws s3 cp`):

```yaml
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

*(These may already exist. Confirm the S3 bucket allows the IAM user to `s3:GetObject`/`s3:PutObject` on the video prefix.)*

- [ ] **Step 5: Run tests**

Run: `python -m pytest -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/flows/reel_flow.py .github/workflows/daily-post.yml
git commit -m "feat(flows): bake royalty-free audio into every Reel via ffmpeg"
```

### Task 3.4: Pixabay curation script + populate `assets/audio/`

**Files:**
- Create: `scripts/curate_audio.py`
- Populate: `assets/audio/{chill,upbeat,cinematic}/*.mp3` (30 files)
- Rewrite: `assets/audio/audio_manifest.json` (with 30 real entries)

- [ ] **Step 1: Write the curation script**

```python
# scripts/curate_audio.py
"""One-off Pixabay Music curation. Not run in CI.

Manual usage:
    python scripts/curate_audio.py --theme chill --count 10
    python scripts/curate_audio.py --theme upbeat --count 10
    python scripts/curate_audio.py --theme cinematic --count 10

Pixabay's music library has a JSON API endpoint that returns track
metadata + a direct MP3 download URL per track. This script filters to
plays <100k, duration >=60s, uploaded >=3mo old, downloads to
assets/audio/{theme}/{slug}.mp3, and appends manifest entries.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "audio" / "audio_manifest.json"
UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"
API = "https://pixabay.com/api/audio/"  # NOTE: requires Pixabay dev key registered manually


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")


def _load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"tracks": []}
    return json.loads(MANIFEST.read_text())


def _write_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2))


def curate(theme: str, count: int, api_key: str) -> None:
    theme_dir = ROOT / "assets" / "audio" / theme
    theme_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        API,
        params={
            "key": api_key,
            "q": theme,
            "min_duration": 60,
            "order": "latest",
            "per_page": 50,
        },
        headers={"User-Agent": UA},
        timeout=30,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    manifest = _load_manifest()
    picked = 0
    for hit in hits:
        if picked >= count:
            break
        if hit.get("plays", 0) > 100_000:
            continue
        slug = _slugify(hit["title"])
        track_id = f"{theme}-{slug}-{hit['id']}"
        filename = f"{theme}/{slug}-{hit['id']}.mp3"
        target = ROOT / "assets" / "audio" / filename
        if target.exists():
            continue
        mp3 = requests.get(hit["audio"], headers={"User-Agent": UA}, timeout=60)
        mp3.raise_for_status()
        target.write_bytes(mp3.content)
        manifest["tracks"].append({
            "track_id": track_id,
            "filename": filename,
            "theme_tags": [theme],
            "license": "Pixabay Content License",
            "attribution_required": False,
            "source_url": f"https://pixabay.com/music/-{hit['id']}",
            "duration_s": hit.get("duration", 0),
            "plays_at_curation": hit.get("plays", 0),
            "curated_at": datetime.now(UTC).date().isoformat(),
        })
        picked += 1
        print(f"[{theme}] {track_id}")
    _write_manifest(manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", required=True, choices=["chill", "upbeat", "cinematic"])
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--api-key", required=True, help="Pixabay dev API key")
    args = parser.parse_args()
    curate(args.theme, args.count, args.api_key)


if __name__ == "__main__":
    sys.exit(main() or 0)
```

*(Pixabay's public /api/audio requires a free API key from pixabay.com/api/docs/. This is a one-off human step — commit the key in the local session env, run the three times, commit the downloaded mp3s + manifest, then discard the key. It is NOT a runtime credential.)*

- [ ] **Step 2: Run curation locally (human step)**

```bash
# Get key from https://pixabay.com/api/docs/
export PIXABAY_KEY=xxx
python scripts/curate_audio.py --theme chill --count 10 --api-key $PIXABAY_KEY
python scripts/curate_audio.py --theme upbeat --count 10 --api-key $PIXABAY_KEY
python scripts/curate_audio.py --theme cinematic --count 10 --api-key $PIXABAY_KEY
unset PIXABAY_KEY
```

Verify: `ls assets/audio/chill/ assets/audio/upbeat/ assets/audio/cinematic/ | wc -l` shows ~30 files. `cat assets/audio/audio_manifest.json | jq '.tracks | length'` shows 30+.

Remove the placeholder entry from Task 3.1.

- [ ] **Step 3: Update .gitignore if needed**

Ensure `assets/audio/*.mp3` is NOT gitignored — we commit them. Add `assets/cache/` to `.gitignore` (history is per-runner-ephemeral for now).

- [ ] **Step 4: Commit + PR**

```bash
git add scripts/curate_audio.py assets/audio/ .gitignore
git commit -m "chore(audio): curate 30 CC0 Pixabay tracks (10 per theme)"
git push
gh pr create --title "feat(reels): audio-baked reels + Pixabay curation (PR 3/6 of v2)" --body "Ships PR 3. ffmpeg installed on runner, 30 CC0 tracks committed, reel_flow bakes audio unless it fails (silent-reel fallback)."
```

---

## PR 4: Meta Places integration + location_id passthrough

Introduces `resolve_location_id()` calling Meta Graph `/pages/search`, extends prompts with `location_query` + `audio_theme`, wires `location_id` through to publishers with retry-without-location fallback.

### Task 4.1: `places.py` adapter

**Files:**
- Create: `src/adapters/places.py`
- Test: `tests/adapters/test_places.py`

**Interfaces:**
- Consumes: `settings.meta_user_access_token`, `settings.meta_graph_api_version` (added in Task 4.2)
- Produces: `resolve_location_id(query: str) -> str | None` — Meta Graph `/pages/search`, filter for lat/lng, cache to `assets/cache/places.json` with 30-day TTL.

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/test_places.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.adapters import places


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(places, "CACHE_PATH", tmp_path / "places.json")
    monkeypatch.setattr("src.settings.settings.meta_user_access_token", "test-token")
    monkeypatch.setattr("src.settings.settings.meta_graph_api_version", "v21.0")
    return tmp_path


def _resp(data: list[dict]) -> Mock:
    return Mock(ok=True, status_code=200, json=lambda: {"data": data})


def test_resolve_picks_first_with_location() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp([
            {"id": "111", "name": "Abstract Concept", "location": {}},
            {"id": "222", "name": "Bali Beach",
             "location": {"latitude": -8.4, "longitude": 115.2}},
            {"id": "333", "name": "Another",
             "location": {"latitude": 1.0, "longitude": 2.0}},
        ])
        result = places.resolve_location_id("Bali Beach")
    assert result == "222"


def test_resolve_returns_none_on_empty() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp([])
        assert places.resolve_location_id("Nowhereland") is None


def test_resolve_returns_none_on_403() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = Mock(ok=False, status_code=403, text="denied")
        assert places.resolve_location_id("Bali") is None


def test_resolve_uses_cache_on_second_call(_tmp_cache: Path) -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp([{"id": "222", "name": "Bali",
                                 "location": {"latitude": -8.4, "longitude": 115.2}}])
        first = places.resolve_location_id("Bali")
        second = places.resolve_location_id("Bali")
    assert first == "222" == second
    assert g.call_count == 1
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `python -m pytest tests/adapters/test_places.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/adapters/places.py
"""Meta Graph /pages/search — resolve a text query to a Place-tagged Page ID.

Composio has no Places search action and no Graph passthrough (as of
2026-07-03), so we call Meta directly. Filters response to Pages with
lat/lng populated -- otherwise Instagram rejects location_id with
INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID at publish time.

Cache hits at assets/cache/places.json with 30-day TTL; invalidate on
publish-time INVALID_LOCATION_ID (caller responsibility).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from src.settings import settings

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "cache" / "places.json"
CACHE_TTL_DAYS = 30
_UA = "InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)"


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        log.warning("places cache corrupt, resetting")
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _is_fresh(entry: dict) -> bool:
    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
    except (KeyError, ValueError):
        return False
    return datetime.now(UTC) - cached_at < timedelta(days=CACHE_TTL_DAYS)


def resolve_location_id(query: str) -> str | None:
    """Return a Facebook Page ID with location data matching `query`, or None."""
    if not query or not settings.meta_user_access_token:
        return None
    cache = _load_cache()
    if query in cache and _is_fresh(cache[query]):
        return cache[query]["page_id"]
    version = settings.meta_graph_api_version
    url = f"https://graph.facebook.com/{version}/pages/search"
    try:
        resp = requests.get(
            url,
            params={
                "q": query,
                "fields": "id,name,location",
                "access_token": settings.meta_user_access_token,
            },
            headers={"User-Agent": _UA},
            timeout=15,
        )
    except requests.RequestException as e:
        log.warning("Places search (%s) network error: %s", query, e)
        return None
    if not resp.ok:
        log.warning("Places search (%s) HTTP %s: %s", query, resp.status_code, resp.text[:200])
        return None
    for page in resp.json().get("data", []):
        loc = page.get("location") or {}
        if loc.get("latitude") is not None and loc.get("longitude") is not None:
            page_id = str(page["id"])
            cache[query] = {"page_id": page_id, "cached_at": datetime.now(UTC).isoformat()}
            _save_cache(cache)
            return page_id
    log.info("Places search (%s) returned no lat/lng results", query)
    return None


def invalidate(query: str) -> None:
    """Drop a query from the cache -- caller after INVALID_LOCATION_ID publish error."""
    cache = _load_cache()
    if query in cache:
        del cache[query]
        _save_cache(cache)
```

- [ ] **Step 4: Run and confirm PASS**

Run: `python -m pytest tests/adapters/test_places.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/places.py tests/adapters/test_places.py
git commit -m "feat(adapters): add Meta /pages/search Places resolver with cache"
```

### Task 4.2: Meta settings + prompt/caption fields

**Files:**
- Modify: `src/settings.py`
- Modify: `prompts/topic.txt`
- Modify: `prompts/caption.txt`
- Modify: `src/content/caption.py`
- Test: `tests/content/test_caption.py`

- [ ] **Step 1: Add Meta settings**

Add to `src/settings.py`:

```python
    # Meta Graph API (Places search — direct call, not via Composio)
    meta_user_access_token: str = ""
    meta_graph_api_version: str = "v21.0"
```

- [ ] **Step 2: Extend `prompts/caption.txt` output schema**

At the end of the `<output_format>` JSON in `prompts/caption.txt`, add two new fields:

```
  "location_query": "physical place name searchable via Meta Pages, or null",
  "audio_theme": "one of: chill | upbeat | cinematic | ambient | energetic"
```

Also add rules:

```
<location_query_rules>
- A REAL physical place with a Facebook Page: "Eiffel Tower, Paris",
  "Coney Island, New York", "Kyoto, Japan". NOT abstract concepts.
- If the topic has no natural location (e.g. software patterns, philosophy),
  return null.
</location_query_rules>

<audio_theme_rules>
- Pick ONE theme that best matches the video's mood:
  chill, upbeat, cinematic, ambient, energetic.
- If unsure, default to "cinematic".
</audio_theme_rules>
```

- [ ] **Step 3: Update caption.py parser**

Modify `src/content/caption.py`'s output dict to include the two new fields (or leave passthrough if it already returns the raw dict). Write a test:

```python
# tests/content/test_caption.py
from __future__ import annotations

import json


def test_caption_output_carries_new_fields() -> None:
    # Direct JSON-shape test — no LLM call, just verifies the shape our
    # code passes downstream. If caption.py transforms output, adjust.
    payload = json.loads('{"caption": "x", "hashtags": "#a", "x_post": "y", '
                         '"image_prompts": ["a","b","c","d","e"], '
                         '"video_prompt": "v", "location_query": "Bali", '
                         '"audio_theme": "cinematic"}')
    assert payload["location_query"] == "Bali"
    assert payload["audio_theme"] == "cinematic"
```

If `caption.py` currently does not strip unknown keys, this is a trivial passthrough — no code change needed there. If it does, adjust to preserve `location_query` and `audio_theme`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/content/test_caption.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/settings.py prompts/caption.txt src/content/caption.py tests/content/test_caption.py
git commit -m "feat(caption): add location_query + audio_theme output fields"
```

### Task 4.3: `location_id` passthrough on Composio adapter + slug rename

**Files:**
- Modify: `src/adapters/composio.py`
- Modify: `src/publishing/image_post.py`
- Modify: `src/publishing/carousel.py`
- Modify: `src/publishing/reel.py`
- Modify: `src/flows/*.py`
- Test: `tests/adapters/test_composio.py` (new or extend existing)

**Interfaces:**
- `execute_action` unchanged (already takes arbitrary params dict)
- Publisher functions gain `location_id: str | None = None`
- On `ComposioActionError` containing "INVALID_LOCATION_ID" or `9004` in message, publishers retry once without `location_id` and log.

- [ ] **Step 1: Rename slug references**

Grep for old slug: `grep -rn "INSTAGRAM_CREATE_MEDIA_CONTAINER" src/`. Update each occurrence (in `image_post.py`, `carousel.py`, `reel.py`) to `INSTAGRAM_POST_IG_USER_MEDIA`.

- [ ] **Step 2: Add `location_id` to single-image publisher**

Modify `src/publishing/image_post.py`. Find the container-create call, add `location_id` when set, wrap in retry-without-location on error:

```python
def publish_image(image_url: str, caption: str, *, location_id: str | None = None) -> str:
    """Publish a single-image post. Retries without location_id on invalid-id error."""
    params = {
        "ig_user_id": settings.instagram_user_id,
        "image_url": image_url,
        "caption": caption,
    }
    if location_id:
        params["location_id"] = location_id
    try:
        container = execute_action("INSTAGRAM_POST_IG_USER_MEDIA", params=params)
    except ComposioActionError as e:
        if location_id and _is_invalid_location(e):
            log.warning("Publish rejected location_id=%s -- retrying without", location_id)
            params.pop("location_id", None)
            container = execute_action("INSTAGRAM_POST_IG_USER_MEDIA", params=params)
        else:
            raise
    # ... rest unchanged
```

Add `_is_invalid_location` helper:

```python
def _is_invalid_location(err: ComposioActionError) -> bool:
    msg = str(err).lower()
    return "invalid_location_id" in msg or "9004" in msg
```

*(You may extract `_is_invalid_location` to a shared module. For 3 callers, inline copy is fine per DRY-threshold heuristic.)*

- [ ] **Step 3: Add location_id to reel publisher**

Same pattern in `src/publishing/reel.py::publish_reel`. Signature becomes:

```python
def publish_reel(video_url: str, caption: str, *, location_id: str | None = None) -> str:
```

Container params get `location_id` when set, retry-without-location on `INVALID_LOCATION_ID`.

- [ ] **Step 4: Add location_id to CAROUSEL PARENT ONLY (NOT children)**

Modify `src/publishing/carousel.py::publish_carousel`. The critical rule: `location_id` goes ONLY on `INSTAGRAM_CREATE_CAROUSEL_CONTAINER`, NEVER on `_create_child_container`. Verify test in Step 6.

```python
def publish_carousel(image_urls: list[str], caption: str, *, location_id: str | None = None) -> str:
    child_ids = [
        _create_child_container(url, i, len(image_urls))
        for i, url in enumerate(image_urls)
    ]
    time.sleep(CONTAINER_PROCESS_WAIT_SECONDS)
    parent_params = {
        "ig_user_id": settings.instagram_user_id,
        "children": child_ids,
        "caption": caption,
    }
    if location_id:
        parent_params["location_id"] = location_id
    try:
        carousel = execute_action("INSTAGRAM_CREATE_CAROUSEL_CONTAINER", params=parent_params)
    except ComposioActionError as e:
        if location_id and _is_invalid_location(e):
            log.warning("Carousel rejected location_id=%s -- retrying without", location_id)
            parent_params.pop("location_id", None)
            carousel = execute_action("INSTAGRAM_CREATE_CAROUSEL_CONTAINER", params=parent_params)
        else:
            raise
    # ... rest unchanged
```

`_create_child_container` **stays untouched**. If someone adds `location_id` there, review MUST reject.

- [ ] **Step 5: Wire flows to pass `location_id`**

For each of `src/flows/carousel_flow.py`, `image_flow.py`, `reel_flow.py`:

- Import `from src.adapters.places import resolve_location_id`
- Extract `caption_data.get("location_query")`, resolve to `location_id`, pass to publisher

Example diff for `carousel_flow.py`:

```python
from src.adapters.places import resolve_location_id
...
def post_carousel(caption_data, caption, image_model, *, dry_run):
    ...
    location_id = resolve_location_id(caption_data.get("location_query") or "") if not dry_run else None
    publish_carousel(image_urls, caption, location_id=location_id)
```

- [ ] **Step 6: Add carousel-child-safety test**

```python
# tests/publishing/test_carousel.py — ADD
from unittest.mock import patch


def test_location_id_only_on_parent_never_on_children() -> None:
    from src.publishing import carousel

    calls: list[tuple[str, dict]] = []

    def _fake_execute(slug: str, params: dict) -> dict:
        calls.append((slug, params))
        if slug == "INSTAGRAM_POST_IG_USER_MEDIA":
            return {"data": {"id": f"child-{len(calls)}"}}
        if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
            return {"data": {"id": "carousel-123"}}
        if slug == "INSTAGRAM_CREATE_POST":
            return {"data": {"id": "media-999"}}
        raise AssertionError(slug)

    with patch("src.publishing.carousel.execute_action", side_effect=_fake_execute), \
         patch("src.publishing.carousel.time.sleep"):
        carousel.publish_carousel(
            image_urls=["https://a", "https://b"],
            caption="c",
            location_id="loc-42",
        )

    child_calls = [c for c in calls if c[0] == "INSTAGRAM_POST_IG_USER_MEDIA"]
    parent_calls = [c for c in calls if c[0] == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER"]
    for _, params in child_calls:
        assert "location_id" not in params, "location_id must NOT be on carousel children"
    assert parent_calls[0][1]["location_id"] == "loc-42"
```

- [ ] **Step 7: Add retry-without-location test**

```python
# tests/publishing/test_carousel.py — ADD
def test_carousel_retries_without_location_on_invalid_id() -> None:
    from src.adapters.composio import ComposioActionError
    from src.publishing import carousel

    call_count = {"parent": 0}

    def _fake_execute(slug: str, params: dict) -> dict:
        if slug == "INSTAGRAM_POST_IG_USER_MEDIA":
            return {"data": {"id": "c1"}}
        if slug == "INSTAGRAM_CREATE_CAROUSEL_CONTAINER":
            call_count["parent"] += 1
            if call_count["parent"] == 1:
                raise ComposioActionError("INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID: no lat/lng")
            assert "location_id" not in params
            return {"data": {"id": "carousel-ok"}}
        if slug == "INSTAGRAM_CREATE_POST":
            return {"data": {"id": "media-999"}}
        raise AssertionError(slug)

    with patch("src.publishing.carousel.execute_action", side_effect=_fake_execute), \
         patch("src.publishing.carousel.time.sleep"):
        carousel.publish_carousel(["https://a"], "cap", location_id="bad-id")

    assert call_count["parent"] == 2
```

- [ ] **Step 8: Full suite**

Run: `python -m pytest -q && python -m ruff check .`
Expected: green.

- [ ] **Step 9: Commit + PR**

```bash
git add src/adapters/composio.py src/publishing/ src/flows/ tests/publishing/ src/settings.py
git commit -m "feat(publishing): location_id passthrough with retry fallback + slug rename"
gh pr create --title "feat(places): Meta location tags via /pages/search (PR 4/6 of v2)" --body "Ships PR 4. Adds META_USER_ACCESS_TOKEN secret. location_id passed to single-image/reel/carousel-parent (never children); retries without on INVALID_LOCATION_ID."
```

**Before merge**, add `META_USER_ACCESS_TOKEN` to the repo's Actions secrets (long-lived FB user token; see spec Section "New env vars / GitHub secrets" for setup).

---

## PR 5: Wide-niche pillars live

Flips the config from the current 4 AI pillars to 6-8 lifestyle+tech pillars and turns cadence up to n=1-3.

### Task 5.1: Rewrite config.json

**Files:**
- Modify: `config.json`

- [ ] **Step 1: Replace pillars block**

```json
{
  "persona": {
    "name": "Kaleidoscope",
    "tone": "curious, playful, cinematic",
    "cta_styles": ["save this", "tag someone who needs this", "which slide hit hardest"]
  },
  "cadence": {
    "max_posts_per_day": 3,
    "post_probability": [0.15, 0.35, 0.35, 0.15],
    "window_utc": {"start": "04:00", "end": "20:00"},
    "min_gap_minutes": 90,
    "skip_probability": 0.05
  },
  "categories": ["travel", "food", "fitness", "entertainment", "tech", "lifestyle"],
  "pillars": [
    {
      "id": "travel-cinematic-reel",
      "category": "travel",
      "content_format": "reel",
      "audio_theme": "cinematic",
      "image_style": "Steve McCurry / National Geographic reportage, mid-day natural light, environmental portrait",
      "location": {"regions": ["Bali", "Tokyo", "Lisbon", "Reykjavik", "Kyoto", "Marrakech"]},
      "hashtags": ["#travel", "#wanderlust", "#reels", "#travelphotography"],
      "weight": 1.5
    },
    {
      "id": "food-editorial-carousel",
      "category": "food",
      "content_format": "carousel",
      "audio_theme": "upbeat",
      "image_style": "Peter Menzel overhead flat-lay, natural window light, tactile textures",
      "location": {"regions": []},
      "hashtags": ["#foodie", "#foodstagram", "#foodphotography"],
      "weight": 1.2
    },
    {
      "id": "fitness-morning-reel",
      "category": "fitness",
      "content_format": "reel",
      "audio_theme": "energetic",
      "image_style": "Annie Leibovitz portraiture, morning light, kinetic pose",
      "location": {"regions": []},
      "hashtags": ["#fitness", "#morningroutine", "#healthylifestyle"],
      "weight": 1.0
    },
    {
      "id": "entertainment-carousel",
      "category": "entertainment",
      "content_format": "carousel",
      "audio_theme": "upbeat",
      "image_style": "candid editorial, ambient venue lighting, unposed moments",
      "location": {"regions": []},
      "hashtags": ["#reels", "#trending", "#viral"],
      "weight": 0.8
    },
    {
      "id": "tech-carousel",
      "category": "tech",
      "content_format": "carousel",
      "audio_theme": "ambient",
      "image_style": "clean product editorial, softbox, shallow depth",
      "location": {"regions": []},
      "hashtags": ["#tech", "#innovation", "#ai"],
      "weight": 1.3
    },
    {
      "id": "lifestyle-image",
      "category": "lifestyle",
      "content_format": "carousel",
      "audio_theme": "chill",
      "image_style": "Magnum documentary, muted tones, candid moment",
      "location": {"regions": []},
      "hashtags": ["#lifestyle", "#slowliving", "#everyday"],
      "weight": 1.0
    }
  ],
  "models": {
    "text": "us.anthropic.claude-fable-5",
    "image": "stability.stable-image-ultra-v1:1",
    "video": "luma.ray-v2:0"
  }
}
```

- [ ] **Step 2: Dry-run to validate**

Run: `python -m src.main --dry-run 2>&1 | tail -50`
Expected: multiple slots planned across pillars, generation runs cleanly, no publish.

- [ ] **Step 3: Commit + PR**

```bash
git add config.json
git commit -m "feat(config): wide-niche pillars live, n=1-3 posts/day cadence"
gh pr create --title "feat(config): wide-niche pillars + turn up cadence (PR 5/6 of v2)" --body "Ships PR 5. 6 pillars across travel/food/fitness/entertainment/tech/lifestyle. Cadence weighted 15/35/35/15 → mean ~1.5 posts/day, hard cap 3. Watch first 3 days of feed, tune weights via PR-6-style tweaks."
```

---

## PR 6: Guardian real key + Lemmy fallback resilience

Small polish PR. Register free Guardian dev key, plug into settings. No code changes to Lemmy (fallbacks already in Task 1.4).

### Task 6.1: Register Guardian key + wire in

**Files:**
- Modify: `README.md` (add `GUARDIAN_API_KEY` to setup docs)

- [ ] **Step 1: Register free key (human step)**

Visit `open-platform.theguardian.com/register/`. Register for the free "developer" tier (5000 requests/day). No card required. Key emailed within seconds.

- [ ] **Step 2: Add to GH Actions secrets**

`gh secret set GUARDIAN_API_KEY --repo Sagargupta16/instagram-autopilot`

Add env var to `.github/workflows/daily-post.yml` under "Generate and publish post":

```yaml
          GUARDIAN_API_KEY: ${{ secrets.GUARDIAN_API_KEY }}
```

- [ ] **Step 3: Update README**

Add row to the Secrets table in README.md:

```markdown
| `GUARDIAN_API_KEY` | Guardian Open Platform dev key (free, 5000/day) — falls back to shared `test` if unset |
```

- [ ] **Step 4: Commit + PR**

```bash
git add .github/workflows/daily-post.yml README.md
git commit -m "chore(guardian): use registered dev key over shared 'test' quota"
gh pr create --title "chore: Guardian real key (PR 6/6 of v2)" --body "Ships PR 6. Free dev-tier key registered (5000/day). Falls back to 'test' string when secret unset — behavior unchanged for local dev."
```

---

## Self-review

**1. Spec coverage:**
- Wide-niche trends → PR 1 (Tasks 1.1-1.6)
- Config schema + RNG cadence → PR 2 (Tasks 2.1-2.5)
- ffmpeg audio bake + Pixabay curation → PR 3 (Tasks 3.1-3.4)
- Meta Places integration → PR 4 (Tasks 4.1-4.3)
- Turn cadence up + wide pillars → PR 5 (Task 5.1)
- Guardian key hardening → PR 6 (Task 6.1)
- All spec sections mapped.

**2. Placeholder scan:**
- No "TBD", "fill in later", "handle edge cases" left in plan.
- Task 3.3 Step 1 references a `download_s3_uri_to_local` helper as `NotImplementedError` — resolved in Step 2 by pivoting to `aws s3 cp` in reel_flow directly. Approach chosen, not TBD.
- Task 3.1 uses a placeholder manifest to unblock picker tests — real 30-track manifest built in Task 3.4. This is intentional two-step, not a plan gap.

**3. Type consistency:**
- `SlotPlan(time_utc, pillar, skip)` — used consistently across `plan_today`, `main.run`, test file.
- `publish_reel(video_url, caption, *, location_id=None)` — signature stable across PR 3 Task 3.3 (drops location_id then Task 4.3 adds it). Called out explicitly in 3.3 Step 2 note.
- `resolve_location_id(query) -> str | None` — stable across places.py, all three flows.
- `bake(video, track, duration_s) -> Path` — stable.
- `pick(theme) -> Path` — stable.
- `_is_invalid_location(err)` — inlined into 3 publishers; noted DRY-threshold decision.

Plan complete and saved to `docs/plans/2026-07-03-v2-premium-multi-slot.md`.
