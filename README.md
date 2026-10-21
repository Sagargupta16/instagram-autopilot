# Instagram Autopilot

An Instagram publisher for a creative data and tech account, powered by AWS Bedrock, headless Chrome, ffmpeg, Cloudinary, and Composio. It posts animated SVG Reels: how-it-works explainers, one-number stat stories, and short timelines, with every number on screen traced to fetched source text.

## Current behavior

- Five weighted pillars, all animated SVG Reels:

  | Pillar | Format | Weight | Audio theme | Evidence |
  | --- | --- | --- | --- | --- |
  | `tech-explainer` | Steps: 3 to 6 icon rows joined by connectors; a packet travels to each new step, whose short detail shows only while it is active | 1.0 | chill | Tech feeds (Hugging Face, Product Hunt, GitHub, Hacker News, Google News, Guardian, Lemmy) or an evergreen mechanism |
  | `cool-stats` | One stat story with an optional icon: big-number count-up, up to 6 ranked bars, a percent ring, or a line that draws in | 1.5 | upbeat | Google News, Guardian and Lemmy records that state the number |
  | `history-timeline` | "The story of X": 4 to 6 dated milestones down a rail of icon nodes | 0.8 | cinematic | Trending Wikipedia articles with their lead sections, Guardian, Lemmy |
  | `tech-versus` | "X vs Y": two named things with optional icons, compared on 3 or 4 aspects in rows; each row lights up in turn and its right-hand cell arrives when the narrator reaches it | 1.0 | upbeat | Tech feeds; evergreen pairs (TCP vs UDP) need no source |
  | `myth-vs-fact` | 2 or 3 common beliefs: each shows MYTH, is struck through on its fact beat, and FACT appears beneath it; the final frame shows every myth crossed out above its fact | 1.0 | cinematic | Science and space records that state each fact; the topic step refuses a myth Reel without cited records |

- At most two successful posts per UTC day (about 60% of days plan two, 35% one, 5% none), with a minimum 180-minute interval between actual successful publications. Meta's spam policy names automated high-frequency posting of repetitive content, so a near-zero-follower account stays well below it.
- GitHub Actions checks every 20 minutes during 04:00-20:00 UTC. Each run handles at most one due slot; it never sleeps for hours or bursts overdue posts.
- The daily plan is deterministic. A 40-minute buffer leaves time for a scheduler tick and generation before the window closes. GitHub can delay cron runs; missed slots are not published outside the window.
- Topics use category-relevant, source-balanced discovery. Available URLs, timestamps, publishers and excerpts travel into caption generation. Stat and timeline Reels require evidence that states numbers or dates; with none, the slot fails instead of inventing them.
- Every number, percentage, date and number word in a scene, and in its caption outside links and hashtags, must appear in the adapters' title or excerpt text (a stat must appear in the one record it cites). Content is schema-validated with at most one repair call; anything still ungrounded fails before rendering. The "Source:" line on the last frame and in the caption is built from adapter metadata, not model text.
- Scenes are drawn as self-contained 1080x1920 SMIL SVGs: one type scale in `svg_kit.py` (hook 68-76 px, labels 44-48 px, details 32-34 px, takeaway 42-44 px, nothing under 32 px), every text color at least 4.5:1 and every mark at least 3:1 (also when dimmed), and all text inside the Reels safe area (x 60-1020, y 250-1600). The icon and the diagram carry each beat and the on-screen words stay short (Instagram shows Reels that are mostly text less); the full explanation is in the caption.
  - Icons come from a vendored set of 60 [Lucide](https://lucide.dev) icons (ISC, license in `src/media/lucide/`). The model picks one allowed name per step, milestone or stat headline; an unknown name fails validation and triggers the one repair call. Step icons are 96 px or larger, in the accent color.
  - The hook is readable on the first frame and gets an entrance: each word brightens in turn while its line pops, under a kicker line and an underline sweep. A thin progress bar fills along the top of the safe area, the active step or milestone glows while earlier ones dim, and the last 2 seconds are an end card with the account's handle and "Follow for more facts". The handle is read live from the connected account (a read-only `INSTAGRAM_GET_USER_INFO` call) when the Reel is drawn, so renaming the account needs no code change; if the lookup fails, the card shows the follow line alone rather than a stale name.
  - Three looks (midnight blue, violet, amber, from the svg-forge themes) with their own kicker wording and icon tile shape. Each post takes the look after the last published post's (stored on its receipt), so consecutive posts never look the same.
  - The cover frame is set with `thumb_offset` to half a second into the final hold, so the profile grid shows the complete card instead of the opening frame. Each Reel runs 12 to 21 seconds on one clock without narration (narration lengthens beats to fit). Following the portfolio-react cover scenes, every scene has three flat layers: a faint dot lattice (6%) with one soft accent wash behind the hook, a ghost layer of waiting panels, connectors and nodes (3% fill, 10% hairline) visible from the first frame, and the lit beats on top; line draws and bar growth use an even travel easing while entrances use an ease-out.
- Headless Chrome renders the frames, ffmpeg encodes H.264 High, yuv420p, BT.709, 30 fps with +faststart, licensed music is baked in as AAC 48 kHz stereo with a fade that ends at the Reel's real length, and ffprobe checks the file before upload.
- Every SVG Reel is narrated when the voice model is present. A local [Kokoro](https://github.com/hexgrad/kokoro) voice (Apache-2.0 weights, run through [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) in its own locked Python 3.13 environment, `scripts/narrate.py`) reads the scene's own on-screen words, one line per beat: the hook, each step, milestone or stat line, and the takeaway. Each beat stretches to fit its line, the voice is normalized to -16 LUFS, the music dips under it (sidechain ducking), and the caption ends with "Narration: AI-generated voice." The voice never says a word or number that is not on screen, and any narration failure leaves the Reel music-only instead of skipping it. `NARRATION=false` turns it off; `NARRATION_VOICE` picks another Kokoro voice (default `af_heart`).
- The hook or stat headline may not open with a greeting, filler, a video preamble, "stop scrolling", a hashtag or an emoji, and the caption's first line must be one complete sentence under 125 characters, the part the feed shows before "... more". Either problem gets the one repair call. Captions carry at most five hashtags, Instagram's cap since 2025-12-18.
- SVG Reels never fall back to photos. A failure before the publisher boundary (no audio, no browser or ffmpeg, a layout or render error, an upload error) skips the post; the slot can retry on a later tick within its three-attempt budget.
- Instagram publication is checkpointed durably before the final API request. A missing response never causes blind automatic republishing.
- The carousel, single-image and Luma Reel formats remain in the code and tests as supported `content_format` values, but no configured pillar uses them.

## Architecture

```text
GitHub scheduler -> validated strategy -> claim one due slot
  -> category-relevant source evidence + recent topic history
  -> Bedrock topic -> Bedrock caption + scene, every number grounded in the evidence
  -> 1080x1920 SMIL SVG -> headless Chrome frames -> ffmpeg H.264 + licensed audio
  -> ffprobe spec check -> checked Cloudinary delivery
  -> Instagram Reel container -> readiness checks
  -> durable publishing checkpoint -> publish -> confirmed media receipt
```

`src/adapters` owns service boundaries; `content` owns evidence, generated text, scenes and number grounding; `media` draws, renders and checks assets; `flows` composes generation and publishing; `publishing` validates Instagram actions; `state` provides local and GitHub compare-and-swap storage.

The configured models are in `config.json`. The text model is Claude through Bedrock; the Stable Image Ultra and Luma Ray 2 entries serve the unused photo and Luma formats. X text is generated for reuse; this project does not publish to X.

## Local setup

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required. Rendering SVG Reels also needs Google Chrome or Chromium and `ffmpeg` with `ffprobe` on `PATH`.

```bash
uv sync --frozen
cp .env.example .env
# Configure credentials locally; never commit .env.
uv run --frozen python -m src.main --dry-run
```

Dry-run performs paid text generation and renders locally but **does not upload, publish, or write topic/audio/publication history**. It works even on a day without scheduled posts. Each SVG Reel preview folder under `output/dry-run/` holds `01.mp4`, `reel.svg`, `scene.json` (the scene plus its source records) and `caption.json`; the run outcome is saved as `output/run-summary.json`.

```bash
uv run --frozen python -m src.main --dry-run --pillar cool-stats   # preview one pillar
uv run --frozen python scripts/fetch_audio_catalog.py      # download the licensed music (gitignored)
uv run --frozen python scripts/fetch_voice_model.py        # download the narration voice (gitignored)
uv run --frozen python scripts/render_svg_reel_sample.py   # output/svg-reel-sample, no credentials needed
```

```bash
uv run --frozen python -m src.main                                     # Live: publishes a due slot if eligible
uv run --frozen python -m src.main --pillar history-timeline           # Live: a due slot, with this pillar
uv run --frozen python -m src.main --pillar tech-explainer --post-now  # Live: post now if cap, gap and window allow
```

`--pillar` only changes which pillar fills a slot that is already due; it never creates a slot. `--post-now` (with `--pillar`) is the one exception: the current minute becomes the single slot for that run, still inside the posting window and still subject to the daily cap, the minimum gap, the ledger claim and the durable publishing checkpoint. It refuses with a reason when any of them would be broken.

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

Optional: `META_USER_ACCESS_TOKEN` for location lookup, `GUARDIAN_API_KEY` for that discovery source (the public `test` key is rejected), and the Luma credentials described below. `NICHE`, `CONTENT_TYPES` and `ALLOW_SILENT_REELS` may be set as repository variables.

**Run workflow** accepts `dry_run`, `pillar` and `post_now` in addition to the reconciliation inputs. The workflow installs `ffmpeg` and uses the runner's preinstalled Google Chrome; a missing browser is reported as a warning and SVG Reels are skipped.

The existing `data/posted_topics.json` is migrated without inventing media IDs for legacy posts. New state retains recent attempt history, captions, source evidence, alt text, container IDs, media IDs, and timestamps. Full editorial metadata is kept for the latest 30 resolved receipts; older receipts retain their publication IDs and timestamps until pruning after 90 days. Unresolved publication attempts are retained.

Run summaries distinguish `published`, `preview`, `skipped`, `failed`, and `needs_reconciliation`. Provider failures exit unsuccessfully. Preparation attempts are limited to three per slot to bound repeated generation costs.

## Recovery

A failure before publication can retry on a later tick. A failure after the durable publication checkpoint is treated as uncertain, and further publication pauses until the outcome is reconciled.

Open the state receipt, check the actual Instagram account, then use **Run workflow**:

- `resolve_slot`: the exact receipt key, such as `2026-09-20|12:00|food-editorial-carousel`.
- If it published, supply the confirmed `media_id`.
- If it did not publish, explicitly select `confirm_not_published`.

Reconciliation updates state only; it does not publish a post. See [operations](docs/operations.md) for failure handling and limitations.

## Audio and Reels

SVG Reels need licensed local audio, or `ALLOW_SILENT_REELS=true` (a repository variable for the workflow, an environment setting locally). Muted Reels are shown less, so the shipped setup bakes music into every Reel:

- `assets/audio/catalog.json` (tracked) lists 15 [Mixkit](https://mixkit.co/free-stock-music/) tracks, five each for chill, upbeat and cinematic, with title, artist, listing page, direct download URL, duration and the sha256 of the file. The [Mixkit Stock Music Free License](https://mixkit.co/license/#musicFree) allows "Social Media video posts" and asks for no attribution. It forbids registering the tracks with a rights-management service (Content ID or similar), remixing them into music-only releases, and redistributing the files.
- `scripts/fetch_audio_catalog.py` (standard library only) downloads the catalog into `assets/audio/<theme>/`, keeps a file only when its sha256 matches, and writes `assets/audio/catalog_manifest.json` with the entries the picker reads. **Both are gitignored: this public repository never commits audio.** The publishing and CI workflows restore them from a cache keyed on the catalog and the script and run the fetch only on a cache miss; a failed download never fails the run.
- Instagram's audio name stays "Original audio": the container tool this project keeps using has no `audio_name` field.

The committed `assets/audio/audio_manifest.json` stays valid and empty for hand-curated entries. The curator supports chill, upbeat, cinematic, ambient, and energetic. Existing compatible downloaded tracks can be explicitly imported:

```bash
uv run --frozen python scripts/curate_audio.py --import-legacy assets/audio/manifest.json
```

The importer validates paths, files, schema, and attribution without downloading anything. Required music attribution (for example CC BY tracks) is included in the Reel caption; Mixkit tracks need none. Dry-run never records audio usage or uploads the result.

The Luma Reel format (`content_format: reel`, unused by the shipped pillars) additionally needs `S3_VIDEO_BUCKET` as an `s3://bucket/prefix/` in the model region and AWS IAM credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN`) with read access to generated S3 objects. Bedrock continues using bearer-token authentication; IAM is used only for S3 retrieval.

## Tests

```bash
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
uv run --frozen pytest --cov=src --cov-branch
```

Tests use dummy credentials, disable `.env` loading, and block network connections. CI runs the suite on Python 3.12 and 3.14, requires at least 80% combined statement/branch coverage, and fails on lint, formatting, test, or lock-export drift. Separate CI jobs, one per pillar and run in parallel, each render one sample Reel with real Chrome and ffmpeg on the Ubuntu runner (each in a different look, with music baked in when the audio library is available and narrated when the voice model is), check it with ffprobe, and upload the MP4 and four frames of it (hook entrance, middle, cover frame, end card); the stat job also renders a cover still of every sample in every look. A final job merges them into the `svg-reel-sample` artifact, one folder per sample. A real-render test runs locally when Chrome and ffmpeg are present and is skipped otherwise. Mocked tests do not prove a live account's authorization or provider availability.

## Cost and content quality

SVG Reels make no image or video model calls: each post costs two Bedrock text calls (topic, then caption and scene), plus at most one repair call each. Rendering runs on the Actions runner; a 21-second Reel is 630 frames. Two posts a day at most keeps render minutes and Cloudinary video storage low. For the unused photo formats, five images per post at the former README assumption of $0.14/image would be about $0.70 per post; that is arithmetic, not a current AWS price quote.

Grounding checks that each number appears in the fetched text; it does not prove the source is right, and a headline can be thin. The count-up animation briefly shows intermediate values on its way to the sourced figure. Inspect saved previews when changing editorial direction. There is no automated engagement-measurement loop, and the application does not claim an empirically optimal posting time or guaranteed growth.

## License

[MIT](LICENSE)
