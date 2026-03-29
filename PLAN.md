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
| 0.5 | Python 3.13+ installed locally | [ ] | For local testing |
| 0.6 | Get Composio API key | [ ] | For GitHub Actions secrets |

---

## Phase 1: MVP - Text Posts + Template Images

**Goal: Daily automated posts to Instagram and X with AI-generated text and Pillow template images.**

### 1A: Project Restructure

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Create `config.json` with content pillars | [ ] | Pillars, schedule, persona, tone, hashtags |
| 1.2 | Restructure `src/` to new layout | [ ] | `generator/`, `publisher/`, `utils/` packages |
| 1.3 | Update `requirements.txt` | [ ] | Add `composio-core`, remove `cloudinary`, `edge-tts` |
| 1.4 | Update `pyproject.toml` to Python 3.13 | [ ] | Bump version, update description |
| 1.5 | Create `.env.example` with new env vars | [ ] | `AWS_BEARER_TOKEN_BEDROCK`, `COMPOSIO_API_KEY` |
| 1.6 | Update `.gitignore` | [ ] | Add `output/`, `data/`, `.env` |

### 1B: Content Generation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.7 | Build `src/config.py` | [ ] | Load + validate `config.json`, determine today's pillar |
| 1.8 | Build `src/generator/text.py` | [ ] | Bedrock Claude Sonnet -> Instagram caption + X post + image prompt |
| 1.9 | Build `src/utils/template_image.py` | [ ] | Pillow: generate 1080x1080 image with text overlay |
| 1.10 | Test text generation locally | [ ] | Verify output quality, JSON parsing, tone |
| 1.11 | Test template image generation | [ ] | Verify images look good on mobile |

### 1C: Publishing

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.12 | Build `src/publisher/instagram.py` | [ ] | Composio: create container -> publish |
| 1.13 | Build `src/publisher/twitter.py` | [ ] | Composio: create tweet (text-only for now) |
| 1.14 | Build `src/main.py` orchestrator | [ ] | Config -> generate -> publish pipeline |
| 1.15 | Test Instagram posting locally | [ ] | Verify post appears on `sagar_sethh` |
| 1.16 | Test X/Twitter posting locally | [ ] | Verify tweet appears |

### 1D: Automation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.17 | Create `.github/workflows/daily-post.yml` | [ ] | Cron: Mon-Sat 3:30 AM UTC (9 AM IST) |
| 1.18 | Add `workflow_dispatch` trigger | [ ] | Manual testing from Actions tab |
| 1.19 | Add GitHub secrets | [ ] | `AWS_BEARER_TOKEN_BEDROCK`, `COMPOSIO_API_KEY` |
| 1.20 | Test via `workflow_dispatch` | [ ] | Run manually, verify post appears |
| 1.21 | Enable cron schedule | [ ] | Uncomment schedule trigger |
| 1.22 | Monitor for 3 days | [ ] | Verify daily posts are working |

### 1E: Quality

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.23 | Write unit tests for config loading | [ ] | `tests/test_config.py` |
| 1.24 | Write unit tests for text generation | [ ] | `tests/test_generator.py` (mock Bedrock) |
| 1.25 | Write unit tests for publishers | [ ] | `tests/test_publisher.py` (mock Composio) |
| 1.26 | Tune persona/prompts for natural output | [ ] | Iterate until captions don't sound AI-generated |

---

## Phase 2: AI-Generated Images

**Goal: Replace Pillow template images with AI-generated visuals from Bedrock.**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Build `src/generator/image.py` | [ ] | Bedrock Nova Canvas + Stability AI |
| 2.2 | Build `src/utils/image_host.py` | [ ] | imgbb API: upload base64 -> get public URL |
| 2.3 | Get imgbb API key | [ ] | Free at imgbb.com |
| 2.4 | Add `IMGBB_API_KEY` to GitHub secrets | [ ] | For CI |
| 2.5 | Update `src/main.py` to use AI images | [ ] | Generate image -> host -> post with URL |
| 2.6 | Update `src/publisher/twitter.py` for images | [ ] | Upload media via Composio -> attach to tweet |
| 2.7 | Test image generation quality | [ ] | Infographic vs artistic styles |
| 2.8 | Test full pipeline with images | [ ] | End-to-end: generate text + image -> post |
| 2.9 | Add image style config to `config.json` | [ ] | Infographic for tips, artistic for motivation |
| 2.10 | Monitor for 1 week | [ ] | Verify image quality and posting works daily |

---

## Phase 3: Reels / Short Videos

**Goal: Generate and post Instagram Reels using Bedrock Nova Reel.**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Build `src/generator/reel.py` | [ ] | Bedrock Nova Reel: text prompt -> video |
| 3.2 | Update `config.json` with reel settings | [ ] | Which pillars get reels vs images |
| 3.3 | Update Instagram publisher for Reels | [ ] | `media_type: "REELS"`, `video_url` |
| 3.4 | Handle video processing wait | [ ] | Poll status until FINISHED before publish |
| 3.5 | Test reel generation quality | [ ] | Verify video looks good on mobile |
| 3.6 | Test full pipeline with reels | [ ] | End-to-end: generate -> host -> post as reel |
| 3.7 | Mix content types in schedule | [ ] | e.g., Mon=image, Wed=reel, Fri=carousel |

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
    +-- config.json (pillars, schedule, persona, tone)
    |
    +-- generator/
    |       |-- text.py       (Bedrock: Claude/Nova -> caption + hashtags)
    |       |-- image.py      (Bedrock: Nova Canvas/Stability) [Phase 2]
    |       |-- reel.py       (Bedrock: Nova Reel) [Phase 3]
    |
    +-- publisher/
    |       |-- instagram.py  (Composio: create container -> publish)
    |       |-- twitter.py    (Composio: upload media -> create tweet)
    |
    +-- utils/
            |-- image_host.py      (imgbb temp hosting) [Phase 2]
            |-- template_image.py  (Pillow text-on-image) [Phase 1]
```

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Posting layer | Composio SDK | Already connected to Instagram (`sagar_sethh`), handles auth/tokens |
| Text model | Claude Sonnet 4.6 via Bedrock | Best quality/cost for short-form content |
| Image model | Nova Canvas + Stability AI | Infographics + artistic images |
| Image hosting | imgbb (Phase 2) | Free, direct URLs, auto-expire, no query params |
| Automation | GitHub Actions cron | Free, serverless, version-controlled |
| Config | JSON file in repo | Simple, no DB needed |
| Phase 1 images | Pillow template | Instagram requires images, Pillow is zero-cost |
| No storage | Generate and discard | No archival needed |
| Auth | Bedrock bearer token (ABSK) | Already working, no IAM keys needed |

---

## GitHub Secrets Required

| Secret | Phase | Purpose |
|--------|-------|---------|
| `AWS_BEARER_TOKEN_BEDROCK` | 1 | Bedrock API auth (ABSK token) |
| `AWS_REGION` | 1 | `us-east-1` |
| `COMPOSIO_API_KEY` | 1 | Composio SDK auth |
| `IMGBB_API_KEY` | 2 | Temporary image hosting |

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
