# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fully automated Instagram content bot. A daily cron in GitHub Actions generates an AI topic (grounded in live trends from 5 sources: HuggingFace papers, Product Hunt, GitHub, Hacker News, Reddit), writes a one-liner caption, generates 5 photorealistic AI images via AWS Bedrock Nova Canvas, and publishes a 5-slide carousel via the Composio v3 API.

## Commands

```bash
pip install -r requirements.txt
python -m src.main                          # Full live run (generate + publish)
python -m src.main --dry-run                # Generate only, no publish
python -m pytest                            # Run full test suite
python -m pytest tests/content/             # Tests for one package
python -m pytest tests/publishing/test_carousel.py::TestPublishCarousel::test_multi_step_flow  # Single test
python -m ruff check .                      # Lint
python -m ruff format .                     # Auto-format
```

## Architecture

The project is organized by **bounded context, one external service per layer**. Each directory under `src/` wraps exactly one concern:

```
src/
├── settings.py        # Pydantic settings loaded from .env
├── pillar.py          # config.json loader + today's-pillar routing
├── schedule.py        # apply_jitter() -- randomize post time inside window
├── main.py            # Entry point + run() orchestrator (<70 lines)
│
├── adapters/          # Low-level HTTP clients for external services
│   ├── bedrock.py            # AWS Bedrock (bearer token, no boto3)
│   ├── composio.py           # Composio v3 REST API + ComposioActionError
│   ├── cloudinary_host.py    # Cloudinary image upload
│   ├── hackernews.py         # HN Algolia search
│   ├── reddit.py             # Reddit public JSON
│   ├── huggingface_papers.py # HuggingFace daily papers (trending AI research)
│   ├── producthunt.py        # Product Hunt AI-category atom feed
│   └── github_trending.py    # GitHub search API (topic:generative-ai / llm)
│
├── content/           # Text generation (uses adapters/bedrock)
│   ├── topic.py       # generate_topic() with trend grounding
│   ├── caption.py     # generate_caption() - 5 photoreal image prompts
│   ├── trends.py      # Parallel aggregation across 11 sources / 5 services
│   └── dedup.py       # posted_topics.json (last 500)
│
├── media/             # AI media generation (uses adapters/bedrock)
│   ├── image.py       # Nova Canvas (cfgScale 6.5, aggressive negative prompt)
│   └── video.py       # Nova Reel async + poll
│
├── publishing/        # Instagram publishing (uses adapters/composio)
│   ├── image_post.py  # 2-step: container -> publish
│   ├── carousel.py    # N+2-step: N children -> carousel -> publish
│   └── reel.py        # 2-step with REELS media_type
│
└── flows/             # Orchestration -- no external deps, just composes
    ├── carousel_flow.py
    ├── image_flow.py
    └── reel_flow.py   # Falls back to image_flow if S3 missing
```

## Non-Obvious Cross-File Contracts

### Pillar routing
`config.json` has `pillars[].content_format` which is `"carousel"`, `"image"`, or `"reel"`. `main.py::run()` dispatches to the matching `flows/*_flow.py`. **Default is carousel** — single-image mode is kept but unused by any pillar.

### Claude returns `image_prompts` as a LIST of 5 PHOTOREAL prompts
`prompts/caption.txt` instructs Claude to return `image_prompts: [s1, s2, s3, s4, s5]` (a JSON array, not a string). **ALL FIVE must be photorealistic** (National Geographic / Magnum / Annie Leibovitz references). The template enforces Nova Canvas canonical order: subject -> environment -> pose -> lighting -> camera+lens -> texture. Slides vary across setting/subject/framing/time-of-day but all stay photoreal. Don't reintroduce the old 12-style palette — we ripped it out because mixed styles broke visual coherence.

### Nova Canvas inverts negations — exclusions belong only in negativeText
The caption prompt explicitly forbids `no`/`not`/`without` inside image prompt text. Nova Canvas (and many diffusion models) treats negation words as *keywords to include*, not exclude. Put exclusions in `negativeText` at the image-generation layer (see `src/media/image.py::DEFAULT_NEGATIVE_PROMPT`). If you see `"no text in image"` inside a prompt string, that's the bug.

### Trends grounding spans 5 services / 11 sources
`content/topic.py` calls `fetch_trending_topics()` which parallel-fetches from: HuggingFace daily papers, Product Hunt AI, GitHub (topic:generative-ai + topic:llm), HN search (3 queries), Reddit top (4 subreddits). The topic prompt template contains `{trending_topics}` — Claude uses fresh headlines to pick angles. If any/all sources fail, the code silently passes partial or `[]` results. Don't add "required" error handling here — graceful degradation is intentional. All sources are **no-auth** (no API key, no OAuth) — if adding a new source needs auth, rethink.

### Post-time jitter
`main.py::run()` calls `apply_jitter(settings.post_jitter_max_minutes)` (default 180 min) before publishing. The GitHub Actions cron fires at 15:30 UTC (start of US lunch engagement window); the jitter sleeps 0-180 min so the actual post time varies day-to-day and does not look bot-scheduled. Skipped on `--dry-run`. Workflow `timeout-minutes` must cover jitter + generation (currently 240).

### Composio auth comes from settings
`adapters/composio.py::execute_action(slug, params)` reads `composio_api_key`, `composio_connected_account_id`, `composio_user_id` from `src.settings` directly. Publisher functions pass ONLY the action-specific params. Don't add auth parameters back — that's what the old code did and it's what we just simplified away.

### Composio v3 wraps Instagram errors in 200 responses
When Instagram's Graph API rejects something (bad URL, rate limit, etc.), Composio v3 returns HTTP 200 with `{"successful": false, "error": "..."}`. `execute_action()` raises `ComposioActionError`. Don't assume `data.id` exists — callers should let the error propagate.

### Bedrock uses bearer token, not boto3
All three Bedrock calls (`adapters/bedrock.py`) use `requests.post` with `Authorization: Bearer <AWS_BEARER_TOKEN_BEDROCK>`. The ABSK token is a newer Bedrock auth mechanism. **If you see boto3 being added, that's wrong.**

### Cloudinary is required (not imgbb)
Instagram's Graph API fetches images server-side from the URL we provide. **Meta blocks `i.ibb.co`** with error 9004. `res.cloudinary.com` is trusted. If you swap hosts, verify Meta can fetch the URL *before* rewriting anything — the fail mode is silent until publish time. Don't add retry/fallback logic; fix the host.

### Settings load at import time
`src/settings.py` instantiates `Settings()` at module level. Missing env vars raise ValidationError before any code runs. `tests/conftest.py` uses `os.environ.setdefault()` at the top — before any `from src.*` import — so test collection works.

## Project Rules

### File size
- **Soft limit 200 lines, hard limit 300.**
- If a file hits 200 lines, plan a split before adding more code. Most files here are 30-80 lines by design.

### One external service per directory
- `adapters/` = one file per external service, does nothing but HTTP.
- `content/`, `media/`, `publishing/` = each wraps one external service via its adapter.
- `flows/` = zero external deps, just composes other layers.
- Don't cross the streams (e.g., publisher modules don't call image hosts directly — that's what `flows/` is for).

### Function length
- Target <40 lines per function. If it needs scrolling, split it.

### Tests mirror `src/`
- `src/content/topic.py` → `tests/content/test_topic.py`.
- Top-level tests (`tests/test_pillar.py`) only for top-level modules (`src/pillar.py`).

### No abbreviations in module names
- `cloudinary_host.py` not `cld.py`, `carousel.py` not `car.py`.

### No comments that narrate obvious code
- Only write a comment when the WHY is non-obvious (hidden constraint, subtle invariant, known landmine). Don't explain WHAT the code does.

## Important Constraints

- Instagram API: 25 publishes per 24 hours
- Nova Canvas dimensions must be divisible by 16 (repo uses 1024x1024)
- Nova Reel requires an S3 bucket — no workaround, async output only
- Composio v3 rejects `ck_` prefix keys (legacy v1/v2) — must be `ak_`
- Cloudinary free tier: 25 credits/month (~30+ daily posts)
- Image prompts must avoid text/words/letters — Nova Canvas hallucinates gibberish text otherwise (see aggressive `DEFAULT_NEGATIVE_PROMPT` in `src/media/image.py`)

## Coding Conventions

- Type hints on all functions, `from __future__ import annotations` at file top
- f-strings, `pathlib` over `os.path`
- Pydantic for settings; plain dicts for `config.json` (no schema class)
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- No `Co-Authored-By` trailers
