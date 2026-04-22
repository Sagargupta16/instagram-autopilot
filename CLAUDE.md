# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fully automated Instagram content bot. Daily cron in GitHub Actions generates an AI topic, caption, and 5 neon/cinematic images via AWS Bedrock, then publishes a 5-slide carousel via Composio v3. Reels supported but optional (require S3).

## Commands

```bash
pip install -r requirements.txt
python -m src.main                              # Full live run (generate + publish)
python -m src.main --dry-run                    # Generate only, no publish
python -m pytest                                # Run full test suite
python -m pytest tests/test_publisher.py        # Single test file
python -m pytest tests/test_publisher.py::TestInstagramPublisher::test_publish_carousel_multi_step  # Single test
python -m ruff check .                          # Lint
python -m ruff format .                         # Auto-format
```

## Architecture

The pipeline is a linear flow orchestrated by `src/main.py::run()`. Understanding these non-obvious cross-file contracts is essential:

### 1. Pillar routing (config.json -> main.py)

`config.json` has an array of `pillars`, each with `days` (which weekdays it runs), `image_style` (natural-language style directive), and `content_format` (`"carousel"`, `"image"`, or `"reel"`). `get_todays_pillar()` in `src/config.py` matches today's weekday to a pillar. The `content_format` field dispatches to one of `_post_carousel`, `_post_image`, or `_post_reel` in `main.py`. **Default is carousel** (5 slides) — single-image mode still exists but isn't used by any pillar.

### 2. Bedrock via bearer token (no boto3)

All three Bedrock calls (`generator/text.py`, `generator/image.py`, `generator/reel.py`) use plain `requests.post` with `Authorization: Bearer <AWS_BEARER_TOKEN_BEDROCK>`. **No boto3, no IAM keys.** The ABSK token is a newer Bedrock auth mechanism. If you see boto3 being added, that's wrong — keep the bearer-token pattern.

### 3. Prompt chaining (text.py -> image.py)

`generate_caption()` returns a dict containing `image_prompts` (a **list of 5 strings**, not a single string). The caption template at `prompts/caption_prompt.txt` instructs Claude to produce 5 visually distinct prompts for one topic — different angles/perspectives forming a carousel narrative (hook -> details -> close). Each prompt is 400-512 chars with explicit lighting, lens, and composition directives. `generate_image()` is called once per prompt in a loop in `_post_carousel`.

### 4. Composio v3 publishing flows (publisher/instagram.py)

All Composio calls go through `_execute_action()` which posts to `/api/v3/tools/execute/{slug}` with body `{arguments, connected_account_id, user_id}`. It raises `ComposioActionError` when `successful: false` in the response — **don't assume `data.id` exists without checking**, v3 wraps Instagram API errors in a 200 response.

- `publish_image_post` — 2 calls: `INSTAGRAM_CREATE_MEDIA_CONTAINER` -> `INSTAGRAM_CREATE_POST`
- `publish_carousel` — **N+2 calls**: N child containers (each with `is_carousel_item: true`, no caption) -> `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` (caption goes here) -> `INSTAGRAM_CREATE_POST`
- `publish_reel` — 2 calls: media container with `media_type: "REELS"` -> publish (longer `max_wait_seconds` because Instagram transcodes video)

### 5. Image hosting: Cloudinary is required (not imgbb)

Instagram's Graph API fetches images server-side from the URL you provide. **Meta blocks `i.ibb.co` URLs** with error 9004 "The media could not be fetched from this URI". Cloudinary's `res.cloudinary.com` domain is trusted. If you ever switch providers, verify Meta can fetch the URL *before* rewriting anything — the fail mode is silent until publish time. Don't add retry/fallback logic; fix the host.

### 6. Settings (src/config.py)

`Settings()` is instantiated at module-import time. Missing env vars raise pydantic ValidationError before any code runs. Tests use `os.environ.setdefault()` at the top of `tests/conftest.py` (before any `from src.*` import). Required env vars: `AWS_BEARER_TOKEN_BEDROCK`, `COMPOSIO_API_KEY` (must be `ak_` prefix), `COMPOSIO_CONNECTED_ACCOUNT_ID` (must be `ca_` prefix), `COMPOSIO_USER_ID`, `INSTAGRAM_USER_ID`, `CLOUDINARY_*` (3 vars). Optional: `S3_VIDEO_BUCKET` (only for Reels).

### 7. Topic dedup

`data/posted_topics.json` (gitignored) stores the last 500 topics. The prompt template sends the most recent 50 to Claude so it avoids repeats. If you're debugging and see "topic too similar to recent", check/clear this file.

## Important Constraints

- Instagram API: 25 publishes per 24 hours
- Nova Canvas dimensions must be divisible by 16 (repo uses 1024x1024)
- Nova Reel requires an S3 bucket — no workaround, it's async output only
- Composio v3 rejects `ck_` prefix keys (legacy v1/v2) — must be `ak_`
- Cloudinary free tier: 25 credits/month (~30+ daily posts worth)
- Image prompts must avoid text/words/letters — Nova Canvas tends to generate gibberish text otherwise (see aggressive negative_prompt in `generator/image.py`)

## Coding Conventions

- Type hints on all functions, `from __future__ import annotations` at file top
- f-strings, `pathlib` over `os.path`
- Pydantic for settings; plain dicts for config.json (no schema class)
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- No `Co-Authored-By` trailers
- Use `replace_all=False` edits — don't batch changes unrelated to the current task
