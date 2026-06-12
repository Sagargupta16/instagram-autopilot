# Instagram Autopilot

Fully automated Instagram content creation and posting powered by AWS Bedrock AI + Composio v3 API.

Generates topics, captions, premium photoreal AI image carousels (Stable Image Ultra), and optional Reels (Luma Ray 2) daily -- then publishes them automatically via GitHub Actions. Set it up once, it runs every day.

## How It Works

1. **GitHub Actions** triggers daily at 15:30 UTC (9 PM IST), then sleeps a random 0-180 min jitter so posts don't look bot-scheduled
2. **Config** determines today's content pillar and format (carousel, image, or reel)
3. **AWS Bedrock Claude** generates topic, caption, and 5 detailed slide image prompts (photoreal documentary/editorial styling per pillar)
4. **AWS Bedrock Stable Image Ultra** generates a premium 1:1 photoreal image per slide (random seed per slide, aggressive negative prompts)
5. **Cloudinary** hosts the images at public URLs (trusted by Instagram's CDN)
6. **Composio v3 API** publishes to Instagram via two-step container flow

For reel-format pillars, **Bedrock Luma Ray 2** generates a 5s/9s 9:16 video via async S3 output (bucket must be in us-west-2), then publishes as an Instagram Reel.

## Content Pillars

| Day | Pillar | Image Style | Format |
|-----|--------|-------------|--------|
| Monday, Thursday | AI Art Techniques | Editorial documentary photography, Magnum Photos feel | Carousel |
| Tuesday, Friday | Prompt Engineering & Tips | Clean studio editorial, Annie Leibovitz portraiture | Carousel |
| Wednesday, Saturday | New AI Tools & Models | National Geographic reportage, environmental portrait | Carousel |
| Sunday | Creative Experiments & Ideas | Candid street photography, 35mm grain, unposed moments | Carousel |

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
| [AWS Bedrock](https://aws.amazon.com/bedrock/) | AI text (Claude Sonnet 4.6), images (Stable Image Ultra), video (Luma Ray 2) | ~$5-15/mo |
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
| `S3_VIDEO_BUCKET` | S3 bucket (us-west-2) for Luma Ray 2 output (optional) |

### One-Time Composio Setup

1. Create account at [composio.dev](https://composio.dev/)
2. Generate a v3 API key (starts with `ak_`)
3. Connect Instagram (Business/Creator account required)
4. Note the connected account ID (`ca_` prefix) and user ID from the dashboard

## Project Structure

```
config.json                  # Content strategy: pillars, schedule, persona, models
src/
  settings.py                # Pydantic settings (.env)
  pillar.py                  # config.json loader + day-of-week pillar routing
  schedule.py                # Random post-time jitter inside the engagement window
  main.py                    # Orchestrator: pillar -> generate -> flow -> publish
  adapters/                  # One external service each: bedrock, composio,
                             # cloudinary_host + trend sources (hackernews,
                             # github_trending, huggingface_papers, producthunt, reddit)
  content/                   # topic, caption, trends aggregator, dedup history
  media/                     # image (Stable Image Ultra), video (Luma Ray 2)
  flows/                     # carousel_flow, image_flow, reel_flow
  publishing/                # Composio v3 REST API: carousel, image_post, reel

prompts/                     # AI prompt templates with {variable} placeholders
data/                        # Runtime state (posted_topics.json for dedup)
tests/                       # Mirrors src/ layout
.github/workflows/
  daily-post.yml             # Cron: daily 15:30 UTC (9 PM IST) + 0-180 min jitter
  ci.yml                     # Shared Python CI + security scan on push/PR
```

## Customization

- **Content strategy**: Edit `config.json` to change pillars, schedule, persona, tone, and image styles
- **Content format**: Set `content_format` per pillar to `"carousel"`, `"image"`, or `"reel"` in `config.json`
- **Posting schedule**: Adjust cron in `.github/workflows/daily-post.yml` and jitter via `POST_JITTER_MAX_MINUTES`
- **Niche**: Change `NICHE` in `.env` (default: `ai_creativity_and_prompts`)
- **Content types**: Change `CONTENT_TYPES` in `.env` (default: `tip,trick,showcase,tutorial,insight`)
- **AI models**: Change `models` in `config.json` (text, image, video)
- **Image quality**: Tune the negative prompt in `src/media/image.py` for different aesthetics

## Cost Breakdown (Monthly)

| Service | Free Tier | Estimated Cost |
|---------|-----------|---------------|
| AWS Bedrock (Claude Sonnet) | Pay per use | ~$2-5/mo |
| AWS Bedrock (Stable Image Ultra) | Pay per use (~$0.14/image) | ~$3-7/mo |
| AWS Bedrock (Luma Ray 2) | Pay per use | ~$1-5/mo (optional) |
| Composio | Free tier | $0 |
| Cloudinary | 25 credits/mo | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| **Total** | | **~$3-10/mo** |

## License

[MIT](LICENSE)
