# Instagram Autopilot - Complete Build Plan

> Fully automated Instagram content creation and posting using AWS Bedrock.
> Zero ongoing effort after setup. Cost: ~$5-15/month (Bedrock API only).

---

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Completed

---

## Phase 0: Prerequisites

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.1 | Choose a niche | [ ] | Psychology facts, finance tips, tech tips, etc. Pick ONE. |
| 0.2 | Have AWS account with Bedrock access | [x] | Claude + Titan Image models enabled |
| 0.3 | Have GitHub account | [x] | For Actions (free CI/CD cron) |
| 0.4 | Install Python 3.12+ locally | [ ] | For local testing before automation |
| 0.5 | Install ffmpeg locally | [ ] | `winget install ffmpeg` or `choco install ffmpeg` |

---

## Phase 1: Instagram + Facebook Account Setup

**Timeline: Day 1 (30 minutes)**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Create new Instagram account | [ ] | Fresh account, niche-specific username |
| 1.2 | Set profile picture | [ ] | Use Titan Image to generate a logo, or design one |
| 1.3 | Write bio with value proposition | [ ] | What do followers get? 1-2 lines + CTA |
| 1.4 | Switch to Creator/Business account | [ ] | Settings > Account > Switch to Professional |
| 1.5 | Create Facebook Page | [ ] | facebook.com/pages/create, same name as IG |
| 1.6 | Link Instagram to Facebook Page | [ ] | FB Page Settings > Linked Accounts > Instagram |
| 1.7 | Set up Linktree (or similar) for bio link | [ ] | For future affiliate links and monetization |

### Account Warm-Up (CRITICAL - Don't Skip)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.8 | Week 1: Post 1x/day manually | [ ] | Use AI-generated content but post by hand |
| 1.9 | Week 1: Like/comment on 20-30 niche posts daily | [ ] | Engage genuinely, not spam |
| 1.10 | Week 1: Follow 20-30 niche accounts daily | [ ] | Real accounts in your niche |
| 1.11 | Week 2: Increase to 2x/day manual posting | [ ] | Mix: images, carousels, reels |
| 1.12 | Week 2: Continue engagement | [ ] | Reply to any comments on your posts |
| 1.13 | After 2 weeks: Account is "warm" | [ ] | Safe to start automated posting |

**Why warm up?** Instagram flags brand new accounts that immediately start API posting. The account looks like a bot and gets shadow-banned or suspended. 2 weeks of human behavior establishes trust.

---

## Phase 2: Meta Developer Setup

**Timeline: Day 1-2 (while warming up account)**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Create Meta Developer account | [ ] | developers.facebook.com, use same FB account |
| 2.2 | Verify identity (phone/2FA) | [ ] | Required for app creation |
| 2.3 | Create Meta App (type: Business) | [ ] | Name: "Instagram Autopilot" or similar |
| 2.4 | Add Instagram Graph API product | [ ] | In app dashboard > Add Product |
| 2.5 | Add your IG account as test user | [ ] | Allows testing before app review |
| 2.6 | Generate short-lived access token | [ ] | Graph API Explorer tool |
| 2.7 | Exchange for long-lived token (60 days) | [ ] | See token exchange API call below |
| 2.8 | Get Instagram Business Account ID | [ ] | Via /me/accounts API call |
| 2.9 | Test: make a test API call | [ ] | GET /{ig-user-id}?fields=username |
| 2.10 | Create privacy policy page | [ ] | Use freeprivacypolicy.com, host on GH Pages |
| 2.11 | Record screencast demo of app | [ ] | Required for app review submission |
| 2.12 | Submit for `instagram_content_publish` permission | [ ] | App Review > Permissions |
| 2.13 | Wait for Meta approval (1-4 weeks) | [ ] | Can test with test users while waiting |

### Token Commands Reference

```bash
# Step 2.7: Exchange short-lived token for long-lived (60 days)
curl -s "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=YOUR_APP_ID&\
client_secret=YOUR_APP_SECRET&\
fb_exchange_token=YOUR_SHORT_TOKEN"

# Step 2.8: Get Instagram Business Account ID
# First get Page ID:
curl -s "https://graph.facebook.com/v21.0/me/accounts?access_token=YOUR_TOKEN"
# Then get IG account from page:
curl -s "https://graph.facebook.com/v21.0/PAGE_ID?fields=instagram_business_account&access_token=YOUR_TOKEN"

# Step 2.9: Test API call
curl -s "https://graph.facebook.com/v21.0/IG_USER_ID?fields=username,media_count&access_token=YOUR_TOKEN"
```

---

## Phase 3: Third-Party Service Setup

**Timeline: Day 2 (20 minutes)**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Create Cloudinary account | [ ] | cloudinary.com (free: 25GB storage, 25GB bandwidth/mo) |
| 3.2 | Get Cloudinary API credentials | [ ] | Dashboard > API Keys |
| 3.3 | Test Cloudinary upload manually | [ ] | Upload any image, verify you get a public URL |

---

## Phase 4: Code Setup and Local Testing

**Timeline: Day 2-7**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Clone repo locally | [x] | `git clone` the instagram-autopilot repo |
| 4.2 | Create `.env` from `.env.example` | [ ] | Fill in all credentials |
| 4.3 | Install Python dependencies | [ ] | `pip install -r requirements.txt` |
| 4.4 | Test content generation (Bedrock Claude) | [ ] | Run content_generator.py standalone |
| 4.5 | Test image generation (Bedrock Titan) | [ ] | Run image_generator.py standalone |
| 4.6 | Test TTS generation (edge-tts) | [ ] | Run tts_generator.py standalone |
| 4.7 | Test video creation (ffmpeg) | [ ] | Run video_maker.py standalone |
| 4.8 | Test Cloudinary upload | [ ] | Run media_uploader.py standalone |
| 4.9 | Test Instagram publish (test user) | [ ] | Run instagram_publisher.py with test account |
| 4.10 | Run full pipeline end-to-end | [ ] | `python -m src.main` |
| 4.11 | Verify post appears on Instagram | [ ] | Check the actual Instagram app |
| 4.12 | Tune prompt templates for quality | [ ] | Iterate on prompts/ files until output is good |

### Quality Checklist Before Automating

- [ ] Captions read naturally (not robotic/AI-sounding)
- [ ] Images are visually appealing and on-brand
- [ ] Hashtags are relevant (not spam/banned hashtags)
- [ ] Reels have clear audio and readable subtitles
- [ ] Carousel slides flow logically and are readable
- [ ] No repeated topics in posted_topics.json

---

## Phase 5: GitHub Secrets and Automation

**Timeline: Day 7-8**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Add all secrets to GitHub repo | [ ] | See secrets list below |
| 5.2 | Add repo variables (NICHE, CONTENT_TYPES) | [ ] | Settings > Secrets and Variables > Variables |
| 5.3 | Test `daily-post.yml` via workflow_dispatch | [ ] | Actions tab > Run workflow |
| 5.4 | Verify automated post appears on Instagram | [ ] | Check the app |
| 5.5 | Enable cron schedule | [ ] | Uncomment schedule triggers if disabled |
| 5.6 | Set up token refresh workflow | [ ] | Needs GH_PAT_FOR_SECRETS (PAT with repo scope) |
| 5.7 | Test token refresh workflow | [ ] | Run manually first |

### GitHub Secrets to Configure

```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
META_APP_ID
META_APP_SECRET
CLOUDINARY_CLOUD_NAME
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
GH_PAT_FOR_SECRETS          # GitHub PAT with repo scope (for token refresh)
```

### GitHub Variables to Configure

```
NICHE=psychology_facts       # Your chosen niche
CONTENT_TYPES=fact,tip,carousel,reel
```

---

## Phase 6: Monetization Setup

**Timeline: Week 3-4 (once content is flowing)**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Sign up for Amazon Associates | [ ] | affiliate-program.amazon.com |
| 6.2 | Sign up for 1-2 more affiliate networks | [ ] | Impact, ShareASale, or niche-specific |
| 6.3 | Add affiliate links to Linktree | [ ] | "Recommended books", "My tools", etc. |
| 6.4 | Occasionally mention products in captions | [ ] | Naturally, not spammy |
| 6.5 | Check eligibility for IG Reels bonuses | [ ] | Professional dashboard > Bonuses |
| 6.6 | Set up Gumroad/Lemonsqueezy (optional) | [ ] | For selling digital products later |

---

## Phase 7: Growth and Optimization

**Timeline: Ongoing (Month 2+)**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | Analyze which content types perform best | [ ] | Check IG Insights weekly |
| 7.2 | Adjust CONTENT_TYPES ratio based on data | [ ] | More of what works, less of what doesn't |
| 7.3 | Optimize posting times | [ ] | Check audience active hours in Insights |
| 7.4 | Improve prompt templates based on engagement | [ ] | A/B test different caption styles |
| 7.5 | Add text overlay on images (Pillow) | [ ] | Branded text on generated images |
| 7.6 | Add analytics tracking | [ ] | Log engagement metrics to MongoDB |
| 7.7 | Build simple dashboard (optional) | [ ] | FastAPI + React to view performance |
| 7.8 | Respond to brand deal inquiries | [ ] | Once you hit 5k-10k followers |

---

## Future Enhancements (Backlog)

| Feature | Priority | Notes |
|---------|----------|-------|
| Text overlay on images using Pillow | High | Branded quotes/facts directly on images |
| Auto-reply to comments using Bedrock | Medium | Boost engagement signals |
| Multi-account support | Medium | Run multiple niche pages |
| A/B testing framework for captions | Medium | Test different hooks, CTAs |
| Analytics dashboard (FARM stack) | Low | Track growth, engagement, revenue |
| Auto-adapt posting times from Insights API | Low | Optimize for audience timezone |
| YouTube Shorts cross-posting | Low | Repurpose Reels to YouTube |
| TikTok cross-posting | Low | Same content, different platform |

---

## Architecture

```
                    GitHub Actions (Cron: 2x daily)
                              |
                              v
                   +--------------------+
                   |     src/main.py    |
                   +--------------------+
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
     content_generator  image_generator  tts_generator
     (Bedrock Claude)   (Bedrock Titan)  (edge-tts)
              |               |               |
              v               v               v
         topic + caption   PNG images    MP3 voiceover
              |               |               |
              |               +-------+-------+
              |                       |
              |                       v
              |                 video_maker.py
              |                   (ffmpeg)
              |                       |
              v                       v
         caption text          MP4 video / PNG images
              |                       |
              +----------+------------+
                         |
                         v
                  media_uploader.py
                   (Cloudinary)
                         |
                         v
                   Public URLs
                         |
                         v
              instagram_publisher.py
               (Instagram Graph API)
                         |
                         v
                  Published Post!
```

---

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude text) | Pay per use | ~$3-8/mo (60 posts) |
| AWS Bedrock (Titan Image) | Pay per use | ~$2-5/mo (60 images) |
| Cloudinary | 25GB storage + bandwidth | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| Instagram | Free | $0 |
| Domain (privacy policy) | GitHub Pages | $0 |
| **Total** | | **~$5-15/mo** |

---

## Niche Selection Guide

Pick based on: high engagement + affiliate potential + evergreen content

| Niche | Engagement | Monetization | Content Difficulty |
|-------|-----------|-------------|-------------------|
| Psychology facts | Very High | Books, courses | Easy |
| Finance/money tips | High | Fintech affiliates | Medium |
| Tech tips & tricks | High | Tech affiliates | Easy |
| Fitness/health | Very High | Supplements, programs | Medium |
| Book summaries | High | Book affiliates | Easy |
| Cooking/recipes | High | Kitchen tools | Medium |
| Motivation/quotes | Medium | Low (generic) | Very Easy |
| History facts | Medium | Books | Easy |

**Recommendation**: Psychology facts or finance tips (high engagement + good affiliate potential).
