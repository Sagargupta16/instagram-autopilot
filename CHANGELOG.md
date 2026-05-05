# Changelog

## [0.7.1] - 2026-05-05

### Fixed
- **Nova Canvas `seed` was effectively constant.** The API default is `12` (not random), so every generation started from the same initial noise and images collapsed toward similar compositions across days. `generate_image()` now picks a fresh random seed from `[0, 2_147_483_646]` per call (unless one is explicitly passed).
- **Photorealism was being enforced twice, imperfectly.** The caption prompt + a ~600-char negative prompt were fighting to keep output photoreal when Nova Canvas has a native `style: "PHOTOREALISM"` enum built for exactly this. Added `style: "PHOTOREALISM"` to the request body; trimmed `DEFAULT_NEGATIVE_PROMPT` from ~600 to ~400 chars by removing illustration/cartoon/3D-render exclusions that the style param handles. Caption prompt no longer forces Claude to repeat "photorealistic" in every slide prompt -- that budget now goes to subject/environment specificity.
- **`cfgScale` default 6.5 was smoothing per-slide differences.** Bumped to 7.5 so Claude's 5 deliberately-different prompts render with actually-different compositions. Nova docs describe 4-7 as "balanced" and 8-10 as "strict prompt adherence"; 7.5 is the strict edge without oversaturation.
- **RAI content filter could IndexError.** `result["images"]` can be empty or absent if AWS RAI strips the output. Now raises `RuntimeError` with the upstream error message instead of `IndexError` on `images[0]`.

### Added
- `src/media/image.py`: `style: "PHOTOREALISM"` param, `seed: int | None` kwarg (random per call when None), `SEED_MIN`/`SEED_MAX` constants, defensive RAI-empty handling.
- Tests: `test_image.py` gains `test_sends_photorealism_style`, `test_randomizes_seed_by_default`, `test_different_calls_use_different_seeds`, `test_explicit_seed_is_respected`, `test_raises_when_rai_strips_all_images`, `test_raises_when_images_key_missing`.
- CLAUDE.md: two new "non-obvious contract" sections — "Photorealism comes from the `style` enum, not prompt text" and "Seed must be randomized per call or images collapse".

### Changed
- `prompts/caption.txt`: image_prompts_rules no longer says `ALL FIVE MUST BE PHOTOREALISTIC` (handled by style param); instead tells Claude to spend prompt budget on subject + environment + lighting specificity and not repeat the word "photorealistic".
- `pyproject.toml`: `0.7.0 -> 0.7.1`.

## [0.7.0] - 2026-05-05

### Fixed
- **Images across days looked similar.** Dedup only tracked topics; image prompts themselves had no history. Claude's few-shot examples in `prompts/caption.txt` biased it toward the same subjects/environments (coffee shops, window light, Leica). `dedup.py` now stores `image_prompts` per post, and `caption.py` injects the last ~15 recent prompts into the caption template as a `<recent_scenes_to_avoid>` block with an explicit "pick different subject/environment/framing" rule. **Note:** dedup persistence across CI runs is not wired up (GitHub Actions runners are ephemeral). The in-run variety rules + per-pillar `style_hint` still produce cross-day variety even without history; if topic/scene repeats become a problem, persist `data/posted_topics.json` via a workflow commit-back step, a GH Actions artifact cache, or an external store.
- **`pillar.image_style` was dead config.** Values contradicted the photoreal rule (`"retrofuturist or 3D render -- vary per slide"` vs. the prompt's `ALL FIVE MUST BE PHOTOREALISTIC`), and nothing consumed the field. Replaced all four values with distinct photoreal sub-style flavors (Magnum, Annie Leibovitz, National Geographic, Garry Winogrand) and wired them into the caption prompt as `{style_hint}` so each pillar has a structurally different look.
- **Preflight only covered Bedrock.** A bad Composio key or Cloudinary secret still forced a 0-180 min jitter sleep before failing. Added `composio.verify_auth()` + `cloudinary_host.verify_auth()`, all three called before `apply_jitter()`.
- **No retries on transient publish failures.** One 502 from Composio killed the day. `execute_action()` now retries 5xx and network errors up to 3 times with exponential backoff. Semantic errors (`ComposioActionError` / `successful: false`) are NOT retried.
- **Non-atomic dedup write.** A process kill mid-save could corrupt `posted_topics.json` and lose all history. Writes now use temp-file + rename.
- **Dry runs polluted history.** `generate_topic` saved to history regardless of `--dry-run`. Save now happens in `main.run()` after caption generation and only when `dry_run=False`.
- Version drift: `pyproject.toml` bumped `0.3.0 -> 0.7.0` to match CHANGELOG.
- Docstring drift: `content/trends.py` said "4 sources", actually aggregates from 4 services / 8 tasks.

### Added
- `src/content/dedup.py::load_recent_image_prompts(limit)` -- newest-first flattened list of recent slide prompts for Claude's variety rule.
- `src/content/dedup.py::record_post(topic, image_prompts)` -- single atomic entry point replacing `save_posted_topic`. Automatically migrates legacy list[str] format.
- `prompts/caption.txt` now takes `{style_hint}` (pillar flavor) and `{recent_scenes}` (what to avoid).
- `src/adapters/composio.py::verify_auth()` + `_post_with_retry()`.
- `src/adapters/cloudinary_host.py::verify_auth()` (calls `cloudinary.api.ping`).
- `src/media/image.py::MAX_PROMPT_CHARS` (1000) + truncation guard. Nova Canvas caps at 1024 -- prompts slightly over could silently truncate mid-sentence; now we truncate cleanly with a warning.
- Cloudinary uploads bucketed by `instagram-autopilot/YYYY-MM/` folder for easy cleanup on the free tier.
- Named constants `CONTAINER_PROCESS_WAIT_SECONDS`, `PUBLISH_MAX_WAIT_SECONDS`, `REEL_PUBLISH_MAX_WAIT_SECONDS` in `publishing/*.py` replace magic `time.sleep(3)` / `max_wait_seconds=60` / `120`.
- `src/media/video.py::NOVA_REEL_DIMENSION` constant + module docstring explaining the 1280x720 constraint (Nova Reel v1 does not support 9:16; Instagram Reels will letterbox landscape sources -- acceptable for now since all pillars are currently carousels).
- Tests: new `tests/content/test_dedup.py` (7 cases: empty, record+load, image prompts, limits, MAX_HISTORY cap, legacy migration, atomic write). Retry-path tests in `test_composio.py`. Prompt-truncation tests in `test_image.py`.

### Changed
- `src/main.py::run()` order: preflight all auth -> apply_jitter -> generate topic -> generate caption -> record_post (if not dry_run) -> publish. Previously saved on topic gen, before caption was known.

## [0.6.0] - 2026-05-02

### Changed
- Rewrote `prompts/caption.txt` using Anthropic XML-tag structure (`<role>`, `<rules>`, `<examples>`, `<output_format>`) for stronger adherence
- Caption prompt now enforces Nova Canvas canonical order (subject -> environment -> pose -> lighting -> camera+lens -> texture) with explicit camera/lens/lighting/film-stock vocabulary
- Caption prompt hard-forbids negation words (`no`/`not`/`without`) inside the prompt text -- Nova Canvas inverts negations, so exclusions belong only in `negativeText`
- Rewrote `prompts/topic.txt` using XML structure with few-shot examples tying topics to trending headlines
- Cron schedule moved from 03:30 UTC to 15:30 UTC (start of US lunch engagement window); workflow timeout raised to 240 min to cover jitter

### Added
- `src/adapters/huggingface_papers.py` -- HuggingFace daily papers feed (community-curated trending AI research, no auth)
- `src/adapters/producthunt.py` -- Product Hunt AI-category atom feed (no auth)
- `src/adapters/github_trending.py` -- GitHub search API for trending `generative-ai` / `llm` repos (60 req/hr unauthenticated)
- `src/content/trends.py` now parallel-fetches from 11 sources across 5 services (was 2 services)
- `src/schedule.py` -- `apply_jitter()` randomizes post time 0-180 min inside the engagement window so cron scheduling does not look bot-like
- `POST_JITTER_MAX_MINUTES` env setting (default 180) + workflow wiring
- Tests for all new adapters, schedule, and trends aggregator

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
