# Instagram Autopilot

Fully automated Instagram content creation and posting powered by AWS Bedrock AI + Composio v3 API.

Generates topics, captions, premium AI images (neon/cinematic style via Nova Canvas), and optional Reels (Nova Reel) daily -- then publishes them automatically via GitHub Actions. Set it up once, it runs every day.

## How It Works

1. **GitHub Actions** triggers daily on a cron schedule (9 AM IST)
2. **Config** determines today's content pillar and format (image or reel)
3. **AWS Bedrock Claude** generates topic, caption, and a detailed image prompt (neon, cinematic, futuristic styling)
4. **AWS Bedrock Nova Canvas** generates a premium 1024x1024 AI image (cfgScale 9.0, aggressive negative prompts)
5. **Cloudinary** hosts the image at a public URL (trusted by Instagram's CDN)
6. **Composio v3 API** publishes to Instagram via two-step container flow

For reel-format pillars, **Bedrock Nova Reel** generates a 6-second video via async S3 output, then publishes as an Instagram Reel.

## Content Pillars

| Day | Pillar | Image Style | Format |
|-----|--------|-------------|--------|
| Monday, Thursday | Cognitive Biases | Cinematic photorealism, neon cyberpunk lighting | Image |
| Tuesday, Friday | Relationship Psychology | Surreal 3D render, holographic, futuristic editorial | Image |
| Wednesday, Saturday | Habits & Behavior Change | Hyper-realistic futuristic, neon rim lighting, chrome | Image |
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
| [Composio](https://composio.dev/) | Instagram publishing via v3 REST API | Free tier |
| [Cloudinary](https://cloudinary.com/) | Image hosting (Instagram needs URLs from trusted CDNs) | Free tier |
| [GitHub Actions](https://github.com/features/actions) | Daily cron automation | Free tier |

### GitHub Secrets

Add these in your repo Settings > Secrets and variables > Actions:

| Secret | Purpose |
|--------|---------|
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock API auth (ABSK token) |
| `AWS_REGION` | AWS region (e.g., `us-east-1`) |
| `COMPOSIO_API_KEY` | Composio v3 API key (`ak_` prefix) |
| `COMPOSIO_CONNECTED_ACCOUNT_ID` | Composio connected account (`ca_` prefix) |
| `COMPOSIO_USER_ID` | Composio user ID (from connected account) |
| `INSTAGRAM_USER_ID` | Instagram Business/Creator account user ID |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |
| `S3_VIDEO_BUCKET` | S3 bucket for Nova Reel output (optional) |

### One-Time Composio Setup

1. Create account at [composio.dev](https://composio.dev/)
2. Generate a v3 API key (starts with `ak_`)
3. Connect Instagram (Business/Creator account required)
4. Note the connected account ID (`ca_` prefix) and user ID from the dashboard

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
    instagram.py             # Composio v3 REST API: image posts + Reels
  utils/
    image_host.py            # Cloudinary: bytes -> public URL

prompts/                     # AI prompt templates with {variable} placeholders
data/                        # Runtime state (posted_topics.json for dedup)
.github/workflows/
  daily-post.yml             # Cron: daily 3:30 AM UTC (9 AM IST)
  ci.yml                     # Ruff lint + pytest on push/PR
```

## Customization

- **Content strategy**: Edit `config.json` to change pillars, schedule, persona, tone, and image styles
- **Content format**: Set `content_format` per pillar to `"image"` or `"reel"` in `config.json`
- **Posting schedule**: Adjust cron in `.github/workflows/daily-post.yml`
- **Niche**: Change `NICHE` in `.env` (default: `psychology_facts`)
- **Content types**: Change `CONTENT_TYPES` in `.env` (default: `fact,tip`)
- **AI models**: Change `models` in `config.json` (text, image, video)
- **Image quality**: Tune `cfgScale` in `image.py` and negative prompts for different aesthetics

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet) | Pay per use | ~$2-5/mo |
| AWS Bedrock (Nova Canvas) | Pay per use | ~$1-3/mo |
| AWS Bedrock (Nova Reel) | Pay per use | ~$1-5/mo (optional) |
| Composio | Free tier | $0 |
| Cloudinary | 25 credits/mo | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| **Total** | | **~$3-10/mo** |

## License

[MIT](LICENSE)
