# CLAUDE.md

## Project Overview

Fully automated Instagram + X/Twitter content creation and posting using AWS Bedrock AI + Composio SDK. Generates topics, captions, AI images (Nova Canvas), and optional Reels (Nova Reel) daily -- publishes on a cron schedule via GitHub Actions. Everything is free except the Bedrock API (~$3-10/month).

## Stack

- **Python 3.12+** with type hints, pathlib, pydantic-settings
- **AWS Bedrock**: Claude Sonnet (text), Nova Canvas (images), Nova Reel (videos) -- all via bearer token (ABSK)
- **Composio SDK**: Instagram + X/Twitter publishing (handles auth/tokens)
- **imgbb**: Free image hosting (Instagram requires public URLs)
- **GitHub Actions**: Cron automation (Mon-Sat 9 AM IST)

## Project Structure

```
config.json                 # Content strategy: pillars, schedule, persona, models
src/
  config.py                 # Pydantic settings (.env) + config.json loading
  generator/
    text.py                 # Bedrock Claude: topics, captions, X posts, image/video prompts
    image.py                # Bedrock Nova Canvas: AI image generation (in-memory bytes)
    reel.py                 # Bedrock Nova Reel: async video generation (S3 output)
  publisher/
    instagram.py            # Composio SDK: image posts + Reels (two-step publish)
    twitter.py              # Composio SDK: text posts (graceful skip if not connected)
  utils/
    image_host.py           # imgbb: bytes -> public URL (24h expiry)
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
- **In-memory image pipeline**: Nova Canvas returns base64 -> decode to bytes -> re-encode for imgbb -> Composio posts. No temp files.
- **Prompt chaining**: Claude generates image/video prompts that Nova Canvas/Reel execute
- **Composio two-step Instagram publish**: Create container (draft) -> publish container
- **Reel fallback**: If `S3_VIDEO_BUCKET` not set, reel-format pillars fall back to image posts
- **Topic dedup**: `posted_topics.json` tracks last 500 topics, sends recent 50 to Claude per prompt
- **Prompt templates** in `prompts/` as plain text with `{variable}` placeholders
- **Image hosting**: imgbb with 24h auto-expiry (Instagram fetches during container creation, then hosts its own copy)

## Important Constraints

- Instagram API rate limit: 25 content publishes per 24 hours
- imgbb free tier: 32MB max upload
- Nova Canvas image dimensions must be divisible by 16 (using 1024x1024)
- Nova Reel requires an S3 bucket for async output
- GitHub Actions free tier: 2000 minutes/month
- X/Twitter: 280 weighted chars (emojis/CJK = 2, URLs = 23)
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
- X/Twitter publishing gracefully skips if not connected on Composio
- `S3_VIDEO_BUCKET` is optional -- omit to disable reel generation
