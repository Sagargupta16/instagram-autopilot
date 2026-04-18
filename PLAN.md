# Instagram Autopilot - Build Plan

> Fully automated Instagram + X content creation and posting using AWS Bedrock + Composio SDK.
> Zero ongoing effort after setup. Cost: ~$3-10/month (Bedrock API only).

---

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Completed

---

## Phase 0: Prerequisites

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.1 | AWS account with Bedrock access | [x] | Bearer token (ABSK) working, all models accessible |
| 0.2 | GitHub account | [x] | For Actions (free cron) |
| 0.3 | Composio account with Instagram connected | [x] | Account: `sagar_sethh` (ig_user_id: `25519335194405950`) |
| 0.4 | Connect X/Twitter on Composio | [ ] | Run `COMPOSIO_MANAGE_CONNECTIONS(toolkit="twitter")` |
| 0.5 | Python 3.12+ installed locally | [ ] | For local testing |
| 0.6 | Get Composio API key | [ ] | For GitHub Actions secrets |
| 0.7 | Get imgbb API key | [ ] | Free at imgbb.com, for image hosting |

---

## Phase 1: MVP - Text Posts + Template Images

**Goal: Daily automated posts to Instagram and X with AI-generated text and Pillow template images.**

### 1A: Project Structure

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Create `config.json` with content pillars | [x] | 3 pillars (cognitive biases, relationships, habits), day-of-week schedule, persona, image styles |
| 1.2 | Restructure `src/` to new layout | [x] | `generator/`, `publisher/`, `utils/` packages |
| 1.3 | Update `requirements.txt` | [x] | `composio-core`, `requests`, `Pillow`, `pydantic-settings` |
| 1.4 | Update `pyproject.toml` | [x] | v0.2.0, updated description |
| 1.5 | Create `.env.example` with new env vars | [x] | `AWS_BEARER_TOKEN_BEDROCK`, `COMPOSIO_API_KEY`, `IMGBB_API_KEY` |
| 1.6 | Update `.gitignore` | [x] | Added `*.png` to project-specific ignores |

### 1B: Content Generation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.7 | Build `src/config.py` | [x] | Pydantic settings + config.json loading + pillar scheduling |
| 1.8 | Build `src/generator/text.py` | [x] | Bedrock Claude via bearer token -> topic, caption, X post, image text |
| 1.9 | Build `src/utils/template_image.py` | [x] | Pillow: 1080x1080, gradient bg per pillar, text overlay, watermark |
| 1.10 | Update prompt templates | [x] | Added pillar context, X post generation, image text generation |
| 1.11 | Test text generation locally | [ ] | Verify output quality, JSON parsing, tone |
| 1.12 | Test template image generation | [ ] | Verify images look good on mobile |

### 1C: Publishing

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.13 | Build `src/utils/image_host.py` | [x] | imgbb upload with 24h expiry |
| 1.14 | Build `src/publisher/instagram.py` | [x] | Composio: create container -> publish (two-step) |
| 1.15 | Build `src/publisher/twitter.py` | [x] | Composio: text post, graceful skip if not connected |
| 1.16 | Build `src/main.py` orchestrator | [x] | Pillar -> generate -> image -> host -> publish pipeline |
| 1.17 | Test Instagram posting locally | [ ] | Verify post appears on `sagar_sethh` |
| 1.18 | Test X/Twitter posting locally | [ ] | Verify tweet appears (after connecting X) |

### 1D: Automation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.19 | Create `.github/workflows/daily-post.yml` | [x] | Cron: Mon-Sat 3:30 AM UTC (9 AM IST), workflow_dispatch |
| 1.20 | Delete old `refresh-token.yml` | [x] | No longer needed (Composio handles auth) |
| 1.21 | Add GitHub secrets | [ ] | `AWS_BEARER_TOKEN_BEDROCK`, `COMPOSIO_API_KEY`, `IMGBB_API_KEY`, `AWS_REGION` |
| 1.22 | Test via `workflow_dispatch` | [ ] | Run manually, verify post appears |
| 1.23 | Monitor for 3 days | [ ] | Verify daily posts are working |

### 1E: Quality

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.24 | Write unit tests for config loading | [x] | `tests/test_config.py` -- pillar scheduling, config validation |
| 1.25 | Write unit tests for text generation | [x] | `tests/test_generator.py` + `test_json_extract.py` (mock Bedrock) |
| 1.26 | Write unit tests for publishers | [x] | `tests/test_publisher.py` (mock Composio), `tests/test_utils.py` |
| 1.27 | Tune persona/prompts for natural output | [x] | Anti-AI-voice instructions, specific tone guidance, hashtag tiers |
| 1.28 | Add `--dry-run` mode | [x] | Generate content without publishing, for local testing |
| 1.29 | Add JSON extraction for Bedrock responses | [x] | Handles markdown code fences around JSON |

---

## Phase 2: AI-Generated Images

**Goal: Replace Pillow template images with AI-generated visuals from Bedrock.**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Build `src/generator/image.py` | [x] | Bedrock Nova Canvas via bearer token, returns raw bytes |
| 2.2 | Add `bedrock_image_model_id` to config | [x] | `models.image` in config.json + per-pillar `image_style` |
| 2.3 | Update `src/main.py` to use AI images | [x] | In-memory pipeline: generate -> host -> post (no temp files) |
| 2.4 | Update `src/publisher/twitter.py` for images | [x] | Text-only for now; image attachment deferred to Phase 4 |
| 2.5 | Test image generation quality | [ ] | Needs live testing with real Bedrock API |
| 2.6 | Test full pipeline with images | [ ] | End-to-end: generate text + image -> post |
| 2.7 | Add image style config to `config.json` | [x] | Per-pillar `image_style` (PHOTOREALISM, 3D_ANIMATED_FAMILY_FILM) |
| 2.8 | Monitor for 1 week | [ ] | Verify image quality and posting works daily |

---

## Phase 3: Reels / Short Videos

**Goal: Generate and post Instagram Reels using Bedrock Nova Reel.**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Build `src/generator/reel.py` | [x] | Bedrock Nova Reel: async job + polling, returns S3 URI |
| 3.2 | Update `config.json` with reel settings | [x] | Per-pillar `content_format`: "image" or "reel" |
| 3.3 | Update Instagram publisher for Reels | [x] | `publish_reel()`: `media_type: "REELS"`, `video_url`, `share_to_feed` |
| 3.4 | Handle video processing wait | [x] | Poll with configurable interval + max wait, raises on timeout/failure |
| 3.5 | Test reel generation quality | [ ] | Needs live testing with real Bedrock API + S3 bucket |
| 3.6 | Test full pipeline with reels | [ ] | End-to-end: generate -> host -> post as reel |
| 3.7 | Mix content types in schedule | [x] | `content_format` per pillar in config.json, `_post_reel` falls back to image if no S3 bucket |

---

## Phase 4: Growth and Optimization (Future)

| Feature | Priority | Notes |
|---------|----------|-------|
| Analytics tracking | Medium | Log engagement metrics per post |
| A/B testing for captions | Medium | Test different hooks, CTAs, tones |
| Multi-account support | Low | Run multiple niche pages |
| Auto-adapt posting times | Low | Optimize based on audience timezone |
| YouTube Shorts cross-posting | Low | Repurpose Reels to YouTube |
| TikTok cross-posting | Low | Same content, different platform |
| Comment auto-reply via Bedrock | Low | Boost engagement signals |

---

## Architecture

```
GitHub Actions (cron: Mon-Sat 3:30 AM UTC / 9:00 AM IST)
    |
    v
main.py (orchestrator)
    |
    +-- config.json (pillars, schedule, persona, models, image styles)
    +-- config.py   (pydantic settings from .env)
    |
    +-- generator/
    |       |-- text.py       (Bedrock Claude via bearer token -> topic + caption + X post + image/video prompts)
    |       |-- image.py      (Bedrock Nova Canvas -> AI-generated images, in-memory bytes)
    |       |-- reel.py       (Bedrock Nova Reel -> async job + S3 output)
    |
    +-- publisher/
    |       |-- instagram.py  (Composio SDK: image posts + Reels)
    |       |-- twitter.py    (Composio SDK: text posts, graceful skip)
    |
    +-- utils/
            |-- image_host.py      (imgbb: bytes -> public URL, 24h expiry)
```

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Publishing layer | Composio SDK | Already connected to Instagram (`sagar_sethh`), handles auth/tokens |
| Text model | Claude Sonnet 4.6 via Bedrock | Best quality/cost for short-form content |
| Image model (Phase 2) | Nova Canvas + Stability AI | Infographics + artistic images |
| Image hosting | imgbb | Free, direct URLs, auto-expire, no query params |
| Automation | GitHub Actions cron | Free, serverless, version-controlled |
| Config | JSON file in repo + .env | Strategy in git, secrets in env |
| Image generation | Bedrock Nova Canvas | AI-generated images, in-memory pipeline (no temp files) |
| Video generation | Bedrock Nova Reel | Async S3 output, optional (falls back to image if no bucket) |
| No storage | Generate and discard | No archival needed, imgbb expires in 24h |
| Auth (AWS) | Bedrock bearer token (ABSK) | Already working, simpler than IAM keys |
| Auth (social) | Composio SDK | Single API key for Instagram + X, no token refresh needed |

---

## GitHub Secrets Required

| Secret | Phase | Purpose |
|--------|-------|---------|
| `AWS_BEARER_TOKEN_BEDROCK` | 1 | Bedrock API auth (ABSK token) |
| `AWS_REGION` | 1 | `us-east-1` |
| `COMPOSIO_API_KEY` | 1 | Composio SDK auth |
| `IMGBB_API_KEY` | 1 | Temporary image hosting |
| `S3_VIDEO_BUCKET` | 3 | S3 bucket for Nova Reel output (optional, falls back to image) |

---

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet text) | Pay per use | ~$2-5/mo |
| AWS Bedrock (Nova Canvas images) | Pay per use | ~$1-5/mo (Phase 2) |
| AWS Bedrock (Nova Reel video) | Pay per use | TBD (Phase 3) |
| Composio | Free tier | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| imgbb | Free tier | $0 |
| **Total** | | **~$3-10/mo** |

---

## Composio Integration Notes

### Instagram (Connected)
- Account: `sagar_sethh` (ig_user_id: `25519335194405950`)
- Two-step publish: `INSTAGRAM_POST_IG_USER_MEDIA` -> `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH`
- Image URLs must be direct HTTPS, no query params
- Rate limit: 25 API publishes per 24 hours

### X/Twitter (Not Yet Connected)
- Needs one-time setup: `COMPOSIO_MANAGE_CONNECTIONS(toolkit="twitter")`
- Post flow: `TWITTER_UPLOAD_MEDIA` (Phase 2+) -> `TWITTER_CREATION_OF_A_POST`
- 280 char limit (weighted: emojis/CJK count as 2, URLs as 23)
- Phase 1: text-only posts, graceful skip if not connected
