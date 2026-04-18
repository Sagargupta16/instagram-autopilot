# CLAUDE.md

## Project Overview

Fully automated Instagram content creation and posting using AWS Bedrock AI + Composio v3 REST API. Generates topics, captions, premium AI images (Nova Canvas with neon/cinematic styling), and optional Reels (Nova Reel) daily -- publishes on a cron schedule via GitHub Actions.

## Stack

- **Python 3.12+** with type hints, pathlib, pydantic-settings
- **AWS Bedrock**: Claude Sonnet (text), Nova Canvas (images), Nova Reel (videos) -- all via bearer token (ABSK)
- **Composio v3 REST API**: Instagram publishing (`POST /api/v3/tools/execute/{slug}`)
- **Cloudinary**: Image hosting (Instagram requires public URLs from trusted CDNs)
- **GitHub Actions**: Daily cron automation

## Project Structure

```
config.json                 # Content strategy: pillars, schedule, persona, models
src/
  config.py                 # Pydantic settings (.env) + config.json loading
  generator/
    text.py                 # Bedrock Claude: topics, captions, image/video prompts
    image.py                # Bedrock Nova Canvas: AI image generation (in-memory bytes)
    reel.py                 # Bedrock Nova Reel: async video generation (S3 output)
  publisher/
    instagram.py            # Composio v3 REST API: image posts + Reels (two-step publish)
  utils/
    image_host.py           # Cloudinary: bytes -> public URL
  main.py                   # Orchestrator entry point

prompts/                    # Prompt templates (topic, caption)
data/                       # Runtime data (posted_topics.json, tracked locally)
.github/workflows/
  daily-post.yml            # Daily content generation + publishing
  ci.yml                    # Ruff lint + pytest on push/PR
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env with all credentials)
python -m src.main

# Dry run (generate without publishing)
python -m src.main --dry-run

# Run tests
python -m pytest

# Lint
python -m ruff check .
```

## Key Patterns

- **Config split**: Content strategy in `config.json` (git-tracked), secrets in `.env` (pydantic-settings)
- **Pillar scheduling**: `config.json` maps days of week to content pillars, each with `image_style` and `content_format`
- **Bedrock via bearer token**: Direct HTTP calls with `Authorization: Bearer <ABSK>`, no boto3/IAM
- **In-memory image pipeline**: Nova Canvas returns base64 -> decode to bytes -> upload to Cloudinary -> Composio posts. No temp files.
- **Prompt chaining**: Claude generates detailed image/video prompts (neon, cinematic, futuristic) that Nova Canvas/Reel execute
- **Composio v3 two-step Instagram publish**: Create container (`INSTAGRAM_CREATE_MEDIA_CONTAINER`) -> publish (`INSTAGRAM_CREATE_POST`)
- **Composio v3 error handling**: `ComposioActionError` raised when `successful: false` in response
- **Reel fallback**: If `S3_VIDEO_BUCKET` not set, reel-format pillars fall back to image posts
- **Topic dedup**: `posted_topics.json` tracks last 500 topics, sends recent 50 to Claude per prompt
- **Prompt templates** in `prompts/` as plain text with `{variable}` placeholders
- **Image quality**: cfgScale 9.0, premium quality, aggressive negative prompts, 400-512 char detailed prompts

## Important Constraints

- Instagram API rate limit: 25 content publishes per 24 hours
- Cloudinary free tier: 25 credits/month (more than enough for daily posts)
- Nova Canvas image dimensions must be divisible by 16 (using 1024x1024)
- Nova Reel requires an S3 bucket for async output
- GitHub Actions free tier: 2000 minutes/month
- New Instagram accounts need 2-week manual warm-up before automated posting

## Coding Conventions

- Type hints on all functions
- f-strings, pathlib over os.path
- Pydantic for settings/validation
- Conventional commits: feat, fix, refactor, docs, test, chore
- No Co-Authored-By trailers in commits
- Secrets in .env only, never committed

## Development Notes

- `.env.example` has all required variables with placeholder values
- `output/` directory is gitignored (temp images)
- `data/posted_topics.json` is gitignored (runtime state)
- `S3_VIDEO_BUCKET` is optional -- omit to disable reel generation
- Composio v3 requires `ak_` prefix API keys and `ca_` nanoid connected account IDs
