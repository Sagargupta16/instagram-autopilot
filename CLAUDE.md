# CLAUDE.md

## Project Overview

Fully automated Instagram + X/Twitter content creation and posting using AWS Bedrock AI + Composio SDK. Generates topics, captions, template images, and publishes on a cron schedule via GitHub Actions. Everything is free except the Bedrock API (~$3-10/month).

## Stack

- **Python 3.12+** with type hints, pathlib, pydantic-settings
- **AWS Bedrock**: Claude Sonnet via bearer token (ABSK) for text generation
- **Composio SDK**: Instagram + X/Twitter publishing (handles auth/tokens)
- **Pillow**: Template image generation (1080x1080 with gradients + text)
- **imgbb**: Free image hosting (Instagram requires public URLs)
- **GitHub Actions**: Cron automation (Mon-Sat 9 AM IST)

## Project Structure

```
config.json                 # Content strategy: pillars, schedule, persona, image styles
src/
  config.py                 # Pydantic settings (.env) + config.json loading
  generator/
    text.py                 # Bedrock Claude: topics, captions, X posts
  publisher/
    instagram.py            # Composio SDK: two-step publish (container -> publish)
    twitter.py              # Composio SDK: text posts (graceful skip if not connected)
  utils/
    template_image.py       # Pillow: 1080x1080 gradient images with text overlay
    image_host.py           # imgbb: upload -> public URL (24h expiry)
  main.py                   # Orchestrator entry point

prompts/                    # Prompt templates (topic, caption, carousel, reel)
data/                       # Runtime data (posted_topics.json, tracked locally)
.github/workflows/
  daily-post.yml            # Daily content generation + publishing
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env with all credentials)
python -m src.main
```

## Key Patterns

- **Config split**: Content strategy in `config.json` (git-tracked), secrets in `.env` (pydantic-settings)
- **Pillar scheduling**: `config.json` maps days of week to content pillars (cognitive biases, relationships, habits)
- **Bedrock via bearer token**: Direct HTTP calls with `Authorization: Bearer <ABSK>`, no boto3/IAM
- **Composio two-step Instagram publish**: Create container (draft) -> publish container
- **Topic dedup**: `posted_topics.json` tracks last 500 topics, sends recent 50 to Claude per prompt
- **Prompt templates** in `prompts/` as plain text with `{variable}` placeholders
- **Image hosting**: imgbb with 24h auto-expiry (Instagram fetches during container creation, then hosts its own copy)

## Important Constraints

- Instagram API rate limit: 25 content publishes per 24 hours
- imgbb free tier: 32MB max upload
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
- Phase 2 will replace Pillow templates with AI-generated images (Bedrock Nova Canvas)
