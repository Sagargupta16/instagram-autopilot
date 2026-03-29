# Instagram Autopilot

Fully automated social media content creation and posting powered by AWS Bedrock AI + Composio SDK.

Generates topics, captions, images, and Reels for Instagram and X (Twitter) - then publishes them on a daily schedule. Set it up once, everything runs on GitHub Actions for free.

## How It Works

1. **GitHub Actions** triggers on a cron schedule (Mon-Sat, 9 AM IST)
2. **Content config** determines today's pillar (DevOps tips, career advice, tool spotlight, etc.)
3. **AWS Bedrock** generates caption, hashtags, and image prompt (Claude Sonnet / Nova Pro)
4. **AWS Bedrock** generates post visuals (Nova Canvas / Stability AI)
5. **Composio SDK** publishes to Instagram and X (Twitter)

## Content Pillars

| Day | Pillar | Tone |
|-----|--------|------|
| Monday, Thursday | DevOps Tips | Educational, practical |
| Tuesday | Career Advice | Motivational, authentic |
| Wednesday | Tool Spotlight | Informative, enthusiastic |
| Friday | Cloud Architecture | Technical, insightful |
| Saturday | Weekend Motivation | Casual, inspiring |
| Sunday | Rest | No post |

All pillars, prompts, hashtags, and tone are configurable in `config.json`.

## Phased Rollout

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Text posts + template images (Pillow) | In progress |
| Phase 2 | AI-generated images (Nova Canvas / Stability) | Planned |
| Phase 3 | Reels / short videos (Nova Reel) | Planned |

## Setup

See [PLAN.md](PLAN.md) for the complete step-by-step build plan.

### Quick Start (Local Testing)

```bash
# Clone and install
git clone https://github.com/Sagargupta16/instagram-autopilot.git
cd instagram-autopilot
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run
python -m src.main
```

### Required Services

| Service | Purpose | Cost |
|---------|---------|------|
| AWS Bedrock | AI text + image generation | ~$3-10/mo |
| Composio | Instagram + X posting (handles auth) | Free tier |
| GitHub Actions | Cron automation | Free |

### GitHub Secrets

```
AWS_BEARER_TOKEN_BEDROCK    # Bedrock API key (ABSK token)
AWS_REGION                  # us-east-1
COMPOSIO_API_KEY            # Composio SDK auth
IMGBB_API_KEY               # Temporary image hosting (Phase 2)
```

## Project Structure

```
src/
  main.py                    # Orchestrator: config -> generate -> post
  config.py                  # Load and validate config.json
  generator/
    text.py                  # Bedrock: topics, captions, hashtags
    image.py                 # Bedrock: AI image generation (Phase 2)
    reel.py                  # Bedrock: video generation (Phase 3)
  publisher/
    instagram.py             # Composio: Instagram posting
    twitter.py               # Composio: X/Twitter posting
  utils/
    image_host.py            # Temporary image hosting for Instagram
    template_image.py        # Pillow: text-on-template for Phase 1

config.json                  # Content pillars, schedule, persona
.github/workflows/
  daily-post.yml             # Cron: generate + publish (Mon-Sat 9AM IST)
```

## Customization

- Edit `config.json` to change pillars, schedule, persona, tone, and hashtags
- Adjust cron schedule in `.github/workflows/daily-post.yml`
- Add new content pillars by extending the `pillars` array in config
- Switch Bedrock models by updating `model` field in config

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

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet text) | Pay per use | ~$2-5/mo |
| AWS Bedrock (Nova Canvas images) | Pay per use | ~$1-5/mo (Phase 2) |
| Composio | Free tier | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| imgbb | Free tier | $0 |
| **Total** | | **~$3-10/mo** |
