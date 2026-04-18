# Instagram Autopilot

Fully automated Instagram + X/Twitter content creation and posting powered by AWS Bedrock AI + Composio SDK.

Generates topics, captions, AI images (Nova Canvas), and optional Reels (Nova Reel) daily -- then publishes them automatically. Set it up once, everything runs on GitHub Actions for free.

## How It Works

1. **GitHub Actions** triggers on a cron schedule (Mon-Sat, 9 AM IST)
2. **Config** determines today's content pillar and format (image or reel)
3. **AWS Bedrock Claude** generates topic, caption, X post, image prompt, and video prompt
4. **AWS Bedrock Nova Canvas** generates a 1024x1024 AI image from the prompt
5. **imgbb** hosts the image at a public URL (24h auto-expiry)
6. **Composio SDK** publishes to Instagram (image post or Reel) and X/Twitter

For reel-format pillars, **Bedrock Nova Reel** generates a 6-second video via async S3 output, then publishes as an Instagram Reel.

## Content Pillars

| Day | Pillar | Image Style | Format |
|-----|--------|-------------|--------|
| Monday, Thursday | Cognitive Biases | Photorealism | Image |
| Tuesday, Friday | Relationship Psychology | 3D Animated | Image |
| Wednesday, Saturday | Habits & Behavior Change | Photorealism | Image |
| Sunday | Rest | -- | No post |

Pillars, persona, tone, image styles, content format, and hashtags are all configurable in `config.json`.

## Setup

### Quick Start

```bash
git clone https://github.com/Sagargupta16/instagram-autopilot.git
cd instagram-autopilot
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

python -m src.main           # Full run
python -m src.main --dry-run # Generate without publishing
```

### Required Services

| Service | Purpose | Cost |
|---------|---------|------|
| [AWS Bedrock](https://aws.amazon.com/bedrock/) | AI text (Claude), images (Nova Canvas), video (Nova Reel) | ~$3-10/mo |
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
| `S3_VIDEO_BUCKET` | S3 bucket for Nova Reel output (optional -- omit to skip reels) |

### One-Time Composio Setup

1. Create account at [composio.dev](https://composio.dev/)
2. Connect Instagram (Business/Creator account required)
3. Optionally connect X/Twitter (the bot gracefully skips if not connected)

## Project Structure

```
config.json                  # Content strategy: pillars, schedule, persona, models
src/
  config.py                  # Pydantic settings (.env) + config.json loader
  main.py                    # Orchestrator: pillar -> generate -> image/reel -> publish
  generator/
    text.py                  # Bedrock Claude: topics, captions, image/video prompts
    image.py                 # Bedrock Nova Canvas: AI image generation (in-memory)
    reel.py                  # Bedrock Nova Reel: async video generation (S3 output)
  publisher/
    instagram.py             # Composio SDK: image posts + Reels
    twitter.py               # Composio SDK: X text posts (graceful skip)
  utils/
    image_host.py            # imgbb: bytes -> public URL (24h auto-expiry)

prompts/                     # AI prompt templates with {variable} placeholders
data/                        # Runtime state (posted_topics.json for dedup)
.github/workflows/
  daily-post.yml             # Cron: Mon-Sat 3:30 AM UTC (9 AM IST)
  ci.yml                     # Ruff lint + pytest on push/PR
```

## Customization

- **Content strategy**: Edit `config.json` to change pillars, schedule, persona, tone, and image styles
- **Content format**: Set `content_format` per pillar to `"image"` or `"reel"` in `config.json`
- **Posting schedule**: Adjust cron in `.github/workflows/daily-post.yml`
- **Niche**: Change `NICHE` in `.env` (default: `psychology_facts`)
- **Content types**: Change `CONTENT_TYPES` in `.env` (default: `fact,tip`)
- **AI models**: Change `models` in `config.json` (text, image, video)

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet) | Pay per use | ~$2-5/mo |
| AWS Bedrock (Nova Canvas) | Pay per use | ~$1-3/mo |
| AWS Bedrock (Nova Reel) | Pay per use | ~$1-5/mo (optional) |
| Composio | Free tier | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| imgbb | Free tier | $0 |
| **Total** | | **~$3-10/mo** |

## License

[MIT](LICENSE)
