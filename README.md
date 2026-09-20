# Instagram Autopilot

An Instagram content pipeline powered by AWS Bedrock, Cloudinary, and Composio. It creates grounded lifestyle topics, coherent five-image editorial carousels, and optional Reels.

## Current behavior

- Six weighted pillars: travel, food, fitness, entertainment, tech, and lifestyle. All currently use carousels.
- Up to two successful posts per UTC day, with a minimum three-hour interval between actual successful publications.
- GitHub Actions checks every 20 minutes during 04:00-20:00 UTC. Each run handles at most one due slot; it never sleeps for hours or bursts overdue posts.
- The daily plan is deterministic. A 40-minute buffer leaves time for a scheduler tick and generation before the window closes. GitHub can delay cron runs; missed slots are not published outside the window.
- Topics use category-relevant, source-balanced discovery. Available URLs, timestamps, and excerpts travel into caption generation. With no suitable evidence, prompts request evergreen content instead of invented breaking news.
- Each carousel has a strong cover, a five-slide progression, concrete takeaways, and distinct scenes with one coherent photographic direction. Image text is not delegated to diffusion. Virality is not guaranteed.
- Images are generated in portrait framing and normalized to validated RGB JPEGs at 1080x1350, below 8 MB. Actual anonymous Cloudinary delivery is checked before Instagram container processing.
- Generated content is schema-validated, with at most one repair call. Five prompts and five aligned alt texts are required. Invalid output fails before image generation.
- Instagram publication is checkpointed durably before the final API request. A missing response never causes blind automatic republishing.

## Architecture

```text
GitHub scheduler -> validated strategy -> claim one due slot
  -> category-relevant source evidence + recent topic history
  -> Bedrock topic + caption + five image prompts + alt text
  -> validated portrait JPEGs -> checked Cloudinary delivery
  -> Instagram draft containers -> readiness checks
  -> durable publishing checkpoint -> publish -> confirmed media receipt
```

`src/adapters` owns service boundaries; `content` owns evidence and generated text; `media` prepares assets; `flows` composes generation and publishing; `publishing` validates Instagram actions; `state` provides local and GitHub compare-and-swap storage.

The configured models are in `config.json`. The defaults remain Claude through Bedrock, Stable Image Ultra, and Luma Ray 2. X text is generated for reuse; this project does not publish to X.

## Local setup

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --frozen
cp .env.example .env
# Configure credentials locally; never commit .env.
uv run --frozen python -m src.main --dry-run
```

Dry-run performs paid text/image generation but **does not upload, publish, or write topic/audio/publication history**. It works even on a day without scheduled posts. Previews and captions are saved under `output/dry-run/`; the run outcome is saved as `output/run-summary.json`.

```bash
uv run --frozen python -m src.main  # Live: publishes a due slot if eligible
```

Local publication records use `data/publication_state.json`. For the same account, all publishers must share the same state backend. Do not run an independent local ledger against an account managed by the GitHub deployment; configure the GitHub state backend when operating that deployment.

Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. `requirements.txt` is a generated, pinned runtime-only export for pip consumers. Regenerate it after intentional dependency changes:

```bash
uv lock
uv export --frozen --no-dev --no-hashes --output-file requirements.txt
```

## GitHub Actions setup

The workflow runs only from `main`. It serializes publishers, uses a frozen runtime installation, and writes durable state to the dedicated `autopilot-state` branch with the workflow token. State is checkpointed during execution; it does not depend on a final history commit step. The branch is created automatically on first use, provided the repository allows the workflow token to write contents.

Required repository secrets:

| Secret | Purpose |
| --- | --- |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock text/image/video generation |
| `AWS_REGION` | Model region; workflow fallback is `us-west-2` |
| `COMPOSIO_API_KEY` | Composio v3 credentials |
| `COMPOSIO_CONNECTED_ACCOUNT_ID` | Connected Instagram account |
| `COMPOSIO_USER_ID` | Composio user |
| `INSTAGRAM_USER_ID` | Instagram Business/Creator account |
| `CLOUDINARY_CLOUD_NAME` | Public media hosting tenant |
| `CLOUDINARY_API_KEY` | Upload credentials |
| `CLOUDINARY_API_SECRET` | Upload credentials |

Optional: `META_USER_ACCESS_TOKEN` for location lookup, `GUARDIAN_API_KEY` for that discovery source, and the Reel credentials described below. `NICHE` and `CONTENT_TYPES` may be set as repository variables.

The existing `data/posted_topics.json` is migrated without inventing media IDs for legacy posts. New state retains recent attempt history, captions, source evidence, alt text, container IDs, media IDs, and timestamps. Full editorial metadata is kept for the latest 30 resolved receipts; older receipts retain their publication IDs and timestamps until pruning after 90 days. Unresolved publication attempts are retained.

Run summaries distinguish `published`, `preview`, `skipped`, `failed`, and `needs_reconciliation`. Provider failures exit unsuccessfully. Preparation attempts are limited to three per slot to bound repeated generation costs.

## Recovery

A failure before publication can retry on a later tick. A failure after the durable publication checkpoint is treated as uncertain, and further publication pauses until the outcome is reconciled.

Open the state receipt, check the actual Instagram account, then use **Run workflow**:

- `resolve_slot`: the exact receipt key, such as `2026-09-20|12:00|food-editorial-carousel`.
- If it published, supply the confirmed `media_id`.
- If it did not publish, explicitly select `confirm_not_published`.

Reconciliation updates state only; it does not publish a post. See [operations](docs/operations.md) for failure handling and limitations.

## Optional Reels

Reels remain off in the shipped strategy. To enable a pillar, set its `content_format` to `reel` and configure:

1. `S3_VIDEO_BUCKET` as an `s3://bucket/prefix/` in the model region.
2. AWS IAM credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_SESSION_TOKEN`) with read access to generated S3 objects. Bedrock continues using bearer-token authentication; IAM is used only for S3 retrieval.
3. ffmpeg and validated local audio assets in `assets/audio/audio_manifest.json`.

The audio manifest ships empty. Missing audio or ffmpeg is detected before paid video generation and falls back to a carousel. The curator supports chill, upbeat, cinematic, ambient, and energetic. Existing compatible downloaded tracks can be explicitly imported:

```bash
uv run --frozen python scripts/curate_audio.py --import-legacy assets/audio/manifest.json
```

The importer validates paths, files, schema, and attribution without downloading anything. Required music attribution is included in the Reel caption. `ALLOW_SILENT_REELS=true` is an explicit optional local setting; the default requires usable audio. Dry-run never records audio usage or uploads the result.

## Tests

```bash
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
uv run --frozen pytest --cov=src --cov-branch
```

Tests use dummy credentials, disable `.env` loading, and block network connections. CI runs the suite on Python 3.12 and 3.14, requires at least 80% combined statement/branch coverage, and fails on lint, formatting, test, or lock-export drift. Mocked tests do not prove a live account's authorization or provider availability.

## Cost and content quality

Five images per post and roughly 30 posts per month means about 150 image generations before filtering or retries. At the former README assumption of $0.14/image, that alone would be about $21/month; this is arithmetic, not a current AWS price quote. Text generation, video, hosting, retries, and Actions usage are additional. Scheduler checks consume Actions minutes even on no-post days.

Source preservation and prompt rules improve factual grounding but do not independently fact-check every claim. Inspect saved previews when changing editorial direction. There is no automated engagement-measurement loop, and the application does not claim an empirically optimal posting time or guaranteed growth.

## License

[MIT](LICENSE)
