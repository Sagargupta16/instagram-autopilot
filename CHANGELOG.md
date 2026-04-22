# Changelog

## [0.5.0] - 2026-04-22

### Changed
- Restructure `src/` into bounded-context layers: `adapters/`, `content/`, `media/`, `publishing/`, `flows/`
- Each directory now wraps exactly one external service or responsibility
- Settings renamed from `config.py` to `settings.py`; pillar routing extracted to `pillar.py`
- Publisher functions no longer take auth parameters -- `adapters/composio.py::execute_action()` reads from settings
- Tests mirror `src/` layout (`tests/content/`, `tests/adapters/`, etc.)
- Every file now under 100 lines (hard project rule: 200 soft limit, 300 hard limit)
- Rename prompts: `topic_prompt.txt` -> `topic.txt`, `caption_prompt.txt` -> `caption.txt`
- Rewrite CLAUDE.md around cross-file contracts + project rules (file size, one-dep-per-dir)

### Added
- `src/adapters/bedrock.py`: unified Bedrock HTTP client (invoke, async, status, extract_json)
- `src/adapters/hackernews.py` + `src/adapters/reddit.py`: split trend sources per service
- `src/content/trends.py`: parallel trend aggregator
- Tests for each adapter, content module, publisher, and flow

### Removed
- `src/generator/`, `src/publisher/`, `src/utils/` (replaced by new layout)
- Auth parameters from publisher function signatures

## [0.4.1] - 2026-04-22

### Changed
- Ground daily topics in live HN + Reddit trends (graceful on failure)
- Caption prompt now mandates 5 VISUALLY DIFFERENT styles from a 12-style palette (not all neon)
- Align pillars + persona to `creativity.prompt` account (AI art, prompts, creative experiments)

### Added
- Trend fetcher pulling from 7 parallel sources (HN search + Reddit top)

## [0.4.0] - 2026-04-18

### Changed
- Migrated from Composio SDK to Composio v3 REST API (`POST /api/v3/tools/execute/{slug}`)
- Switched image hosting from imgbb to Cloudinary (Instagram blocks imgbb URLs)
- Upgraded image quality: cfgScale 9.0, 30+ negative prompt terms, 400-512 char detailed prompts
- Pillar image styles upgraded to neon/cyberpunk/cinematic/futuristic aesthetics
- Image prompt generation now requires lighting, lens, atmosphere, and composition details
- Bumped text generation max_tokens from 1024 to 2048 for richer prompts
- Updated daily workflow schedule and secrets for v3 API + Cloudinary
- Updated CI workflow to use Cloudinary test env vars

### Added
- `ComposioActionError` for proper v3 response error handling (`successful: false`)
- `COMPOSIO_USER_ID` setting (required by v3 API)
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` settings
- Test for Composio v3 error response handling

### Removed
- Twitter/X publishing (`src/publisher/twitter.py`)
- imgbb integration (`IMGBB_API_KEY` setting)
- Composio auth helper (`src/publisher/composio_auth.py`)

## [0.3.0] - 2026-04-18

### Changed
- Replaced Pillow template images with AI-generated images via Bedrock Nova Canvas
- Updated caption prompt to generate `image_prompt` and `video_prompt` instead of `image_text`
- Rewrote `image_host.py` to accept raw bytes instead of file paths (fully in-memory pipeline)
- Rewrote `main.py` orchestrator with separate `_post_image` and `_post_reel` flows
- Updated all tests for new architecture (image generator, reel generator, publisher reels)
- Image dimensions changed from 1080x1080 to 1024x1024 (Nova Canvas requires multiples of 16)

### Added
- `src/generator/image.py` -- Bedrock Nova Canvas image generation (bearer token auth, returns bytes)
- `src/generator/reel.py` -- Bedrock Nova Reel video generation (async job + S3 polling)
- `publish_reel()` in Instagram publisher (REELS media type, share_to_feed)
- Per-pillar `image_style` and `content_format` in config.json
- `models` section in config.json (text, image, video model IDs)
- `S3_VIDEO_BUCKET` env var and GitHub Actions secret (optional, for reel support)
- Negative prompt for Nova Canvas (no text/watermarks/logos in generated images)

### Removed
- `src/utils/template_image.py` (Pillow template generation)
- `prompts/carousel_prompt.txt` and `prompts/reel_prompt.txt` (replaced by caption prompt fields)
- Pillow dependency from requirements.txt
- `image_styles` gradient colors from config.json

## [0.2.0] - 2026-04-06

### Changed
- Replaced direct Instagram Graph API with Composio SDK for publishing
- Replaced boto3/IAM keys with Bedrock bearer token (ABSK) via requests
- Replaced Cloudinary with imgbb for image hosting (free, simpler)
- Restructured src/ into generator/, publisher/, utils/ packages
- Updated prompt templates to generate X/Twitter posts and image overlay text
- Simplified from 8 dependencies to 5 (removed boto3, cloudinary, edge-tts, python-dotenv)
- Updated GitHub Actions workflow with new secrets and removed ffmpeg dependency

### Added
- config.json for content strategy (pillars, schedule, persona, image styles)
- Pillow template image generation (1080x1080 gradient + text overlay per pillar)
- X/Twitter publishing via Composio (graceful skip if not connected)
- Day-of-week content pillar scheduling
- imgbb image upload with 24h auto-expiry

### Removed
- Old scaffold files (content_generator, image_generator, tts_generator, video_maker, media_uploader, instagram_publisher)
- refresh-token.yml workflow (Composio handles auth)
- Cloudinary, edge-tts, ffmpeg, boto3 dependencies

## [0.1.0] - 2026-03-16

- Initial project scaffold with full automation pipeline
