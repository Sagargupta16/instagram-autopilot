# Instagram Autopilot

Fully automated Instagram content creation and posting powered by AWS Bedrock AI.

Generates topics, captions, images, and Reels -- then publishes them on a schedule. Set it up once, pay ~$5-15/month for Bedrock API, everything else is free.

## How It Works

1. **GitHub Actions** triggers on a cron schedule (2x daily)
2. **Bedrock Claude** generates topic, caption, hashtags, and reel scripts
3. **Bedrock Titan Image** generates post visuals
4. **edge-tts** generates voiceover audio (free)
5. **ffmpeg** stitches images + audio into Reel videos
6. **Cloudinary** hosts the media (free tier)
7. **Instagram Graph API** publishes the post

## Content Types

- Single image posts (facts, tips, quotes)
- Carousel posts (multi-slide educational content)
- Reels (image + voiceover + subtitles)

## Setup

See [PLAN.md](PLAN.md) for the complete step-by-step setup guide.

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

### Required Accounts

| Service | Purpose | Cost |
|---------|---------|------|
| AWS (Bedrock) | AI text + image generation | ~$5-15/mo |
| Instagram Business/Creator | Posting target | Free |
| Meta Developer | API access | Free |
| Cloudinary | Media hosting | Free (25GB) |
| GitHub | Automation (Actions) | Free |

### GitHub Secrets

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
```

## Project Structure

```
src/
  config.py                 # Settings from environment variables
  content_generator.py      # Bedrock Claude: topics, captions, scripts
  image_generator.py        # Bedrock Titan Image: post visuals
  tts_generator.py          # edge-tts: voiceover audio
  video_maker.py            # ffmpeg: stitch into Reels
  media_uploader.py         # Cloudinary: host media
  instagram_publisher.py    # Graph API: publish to Instagram
  main.py                   # Orchestrator

prompts/                    # Prompt templates (customize for your niche)
.github/workflows/
  daily-post.yml            # Cron job: generate + publish
  refresh-token.yml         # Cron job: refresh Instagram token
```

## Customization

- Edit files in `prompts/` to change content style and tone
- Set `NICHE` and `CONTENT_TYPES` in GitHub repo variables
- Adjust cron schedule in `.github/workflows/daily-post.yml`
