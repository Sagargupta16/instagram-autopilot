# CLAUDE.md

## Project Overview

Fully automated Instagram content creation and posting using AWS Bedrock AI. Generates topics, captions, images, and Reels on a cron schedule via GitHub Actions. Everything is free except the Bedrock API (~$5-15/month).

## Stack

- **Python 3.12+** with type hints, pathlib, pydantic-settings
- **AWS Bedrock**: Claude (text) + Titan Image (visuals)
- **edge-tts**: Free text-to-speech for Reel voiceovers
- **ffmpeg**: Video stitching (images + audio -> MP4)
- **Cloudinary**: Media hosting (free tier)
- **Instagram Graph API v21.0**: Publishing
- **GitHub Actions**: Cron automation (2x daily)

## Project Structure

```
src/
  config.py                 # Pydantic settings from env vars
  content_generator.py      # Bedrock Claude: topics, captions, carousel, reel scripts
  image_generator.py        # Bedrock Titan Image: post/carousel/reel visuals
  tts_generator.py          # edge-tts: voiceover + subtitle timing
  video_maker.py            # ffmpeg: stitch into Reels
  media_uploader.py         # Cloudinary upload -> public URLs
  instagram_publisher.py    # Graph API: publish image/carousel/reel + token refresh
  main.py                   # Orchestrator entry point

prompts/                    # Prompt templates (topic, caption, carousel, reel)
data/                       # Runtime data (posted_topics.json, tracked locally)
.github/workflows/
  daily-post.yml            # Daily content generation + publishing
  refresh-token.yml         # Instagram token auto-refresh (bi-monthly)
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env with all credentials)
python -m src.main

# Test individual modules
python -c "from src.content_generator import generate_topic; print(generate_topic())"
python -c "from src.image_generator import generate_post_image; generate_post_image('test topic')"
python -c "from src.tts_generator import generate_voiceover; generate_voiceover('Hello world')"
```

## Key Patterns

- All config via environment variables (pydantic-settings), never hardcoded
- Prompt templates live in `prompts/` as plain text with `{variable}` placeholders
- `posted_topics.json` tracks last 500 topics to prevent repeats
- Instagram Graph API requires media at a public URL (Cloudinary), not direct upload
- Long-lived tokens expire in 60 days, auto-refreshed by `refresh-token.yml`
- Content types: `fact`, `tip`, `carousel`, `reel` (configurable via CONTENT_TYPES env var)

## Important Constraints

- Instagram API rate limit: 25 content publishes per 24 hours
- Cloudinary free tier: 25GB storage, 25GB bandwidth/month
- GitHub Actions free tier: 2000 minutes/month
- Titan Image output is good for infographic/aesthetic styles, not photorealism
- Reels require video hosted at a public URL, processing takes 10-60 seconds
- New accounts need 2-week manual warm-up before automated posting (anti-bot measures)

## Coding Conventions

- Type hints on all functions
- f-strings, pathlib over os.path
- Pydantic for settings/validation
- Conventional commits: feat, fix, refactor, docs, test, chore
- No Co-Authored-By trailers in commits
- Secrets in .env only, never committed

## Development Notes

- `.env.example` has all required variables with placeholder values
- `output/` directory is gitignored (temp images, audio, video)
- `data/posted_topics.json` is gitignored (runtime state)
- ffmpeg must be installed locally and in CI (apt-get in workflow)
