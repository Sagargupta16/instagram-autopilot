# Instagram Autopilot

Fully automated Instagram + X/Twitter content creation and posting powered by AWS Bedrock AI + Composio SDK.

Generates topics, captions, and template images daily -- then publishes them automatically. Set it up once, everything runs on GitHub Actions for free.

## How It Works

1. **GitHub Actions** triggers on a cron schedule (Mon-Sat, 9 AM IST)
2. **Config** determines today's content pillar based on day of week
3. **AWS Bedrock** (Claude Sonnet via bearer token) generates topic, caption, X post, and image text
4. **Pillow** generates a branded 1080x1080 template image with gradient + text overlay
5. **imgbb** hosts the image at a public URL (24h auto-expiry)
6. **Composio SDK** publishes to Instagram (two-step: container -> publish) and X/Twitter

## Content Pillars

| Day | Pillar | Style |
|-----|--------|-------|
| Monday, Thursday | Cognitive Biases | Dark blue/red gradient |
| Tuesday, Friday | Relationship Psychology | Purple/teal gradient |
| Wednesday, Saturday | Habits & Behavior Change | Dark purple/blue gradient |
| Sunday | Rest | No post |

All pillars, persona, tone, image styles, and hashtags are configurable in `config.json`.

## Phased Rollout

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Text posts + Pillow template images | Code complete, needs testing |
| Phase 2 | AI-generated images (Nova Canvas / Stability) | Planned |
| Phase 3 | Reels / short videos (Nova Reel) | Planned |

## Setup

### Quick Start

```bash
git clone https://github.com/Sagargupta16/instagram-autopilot.git
cd instagram-autopilot
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

python -m src.main
```

### Required Services

| Service | Purpose | Cost |
|---------|---------|------|
| [AWS Bedrock](https://aws.amazon.com/bedrock/) | AI text generation (Claude Sonnet) | ~$2-5/mo |
| [Composio](https://composio.dev/) | Instagram + X publishing (handles auth/tokens) | Free tier |
| [imgbb](https://imgbb.com/) | Image hosting (Instagram requires public URLs) | Free tier |
| [GitHub Actions](https://github.com/features/actions) | Cron automation | Free tier |

### GitHub Secrets

Add these in your repo Settings > Secrets and variables > Actions:

| Secret | Purpose |
|--------|---------|
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock API auth (ABSK token) |
| `AWS_REGION` | AWS region (e.g., `us-east-1`) |
| `COMPOSIO_API_KEY` | Composio SDK auth |
| `IMGBB_API_KEY` | imgbb image upload |

### One-Time Composio Setup

1. Create account at [composio.dev](https://composio.dev/)
2. Connect Instagram (Business/Creator account required)
3. Optionally connect X/Twitter (the bot gracefully skips if not connected)

## Project Structure

```
config.json                  # Content strategy: pillars, schedule, persona, image styles
src/
  config.py                  # Pydantic settings (.env) + config.json loader
  main.py                    # Orchestrator: pillar -> generate -> image -> host -> publish
  generator/
    text.py                  # Bedrock Claude: topics, captions, X posts
  publisher/
    instagram.py             # Composio SDK: two-step Instagram publish
    twitter.py               # Composio SDK: X text posts (graceful skip)
  utils/
    template_image.py        # Pillow: 1080x1080 branded images per pillar
    image_host.py            # imgbb: upload with 24h auto-expiry

prompts/                     # AI prompt templates with {variable} placeholders
data/                        # Runtime state (posted_topics.json for dedup)
.github/workflows/
  daily-post.yml             # Cron: Mon-Sat 3:30 AM UTC (9 AM IST)
```

## Customization

- **Content strategy**: Edit `config.json` to change pillars, schedule, persona, tone, and image colors
- **Posting schedule**: Adjust cron in `.github/workflows/daily-post.yml`
- **Niche**: Change `NICHE` in `.env` (default: `psychology_facts`)
- **Content types**: Change `CONTENT_TYPES` in `.env` (default: `fact,tip`)
- **AI model**: Change `BEDROCK_MODEL_ID` in `.env` to use a different Claude model

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet) | Pay per use | ~$2-5/mo |
| Composio | Free tier | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| imgbb | Free tier | $0 |
| **Total (Phase 1)** | | **~$2-5/mo** |

## License

[MIT](LICENSE)
