# Operating the publisher

The workflow runs on short scheduler ticks (`7,27,47 4-19 * * *`) and on demand. GitHub's best-effort cron fires only a few of the 48 daily ticks (about four a day, often hours late), so each scheduled run posts the day's planned slot whose time has passed, and the deterministic daily plan reserves 40 minutes at the end for generation. A slot planned after the day's last in-window fire is lost; asking for a Reel ("create one", below) covers that. From 2026-10-24 to 2026-10-27 the workflow ran on demand alone and nothing posted for three days, so both run now. Each run handles one slot, and the ledger enforces spacing from the last confirmed publication (180 minutes), the daily cap (two posts) and the 04:00-20:00 UTC window. The cadence is deliberately low while the account is small: Meta's spam policy names automated high-frequency posting and repetitive content, and Instagram says the creators with the highest follower growth post 10 or more Reels a month, which two a day already exceeds. Raise it only on purpose, keeping `post_probability` one entry longer than `max_posts_per_day`.

## Choosing a pillar and posting on demand

**Run workflow** takes a `pillar` (`cool-stats` by default; `tech-explainer`, `history-timeline`, `tech-versus` or `myth-vs-fact`) and `post_now` (on by default), so pressing it posts a Reel now. From a terminal, or from a Claude Code session asked to "create one":

```bash
gh workflow run daily-post.yml --repo Sagargupta16/instagram-autopilot --ref main -f pillar=tech-versus -f post_now=true
```

With `post_now` off the pillar only swaps the pillar of a slot that is already due; with no due slot the run skips. A slot time filled under one pillar is not filled again under another.

`post_now` together with `pillar` is the single exception to waiting for a planned slot. The current minute becomes the only candidate for that run; it must be inside the posting window, the daily cap and minimum gap are read from the shared GitHub state, and the slot goes through the same ledger claim, durable publishing checkpoint and no-retry rule as a scheduled post. When any of these would be broken the run writes a `refused` summary with the reason and exits non-zero without generating anything. Combine `post_now` with `dry_run` to preview a pillar without touching state.

## Look, cover frame, music and narration

Each SVG Reel uses one of three looks (palette, kicker wording, icon tile shape; `src/media/svg_look.py`). The run picks the look after the one stored on the most recently published receipt, so consecutive posts never share a look; with no such receipt, and in a dry-run, the UTC day number picks it. The dry-run `scene.json` records the look and the cover offset.

The container is created with `thumb_offset` in milliseconds: half a second into the final hold, when the whole scene is on screen and before the 2-second end card. The project keeps the deprecated `INSTAGRAM_CREATE_MEDIA_CONTAINER` tool on purpose: the documentation of its replacement asks for hashtags sent as `%23`, which could cut live captions short. That tool has no `audio_name` field, so the Reel's audio name stays Instagram's default. Before rendering, the flow reads the connected account's username with the read-only `INSTAGRAM_GET_USER_INFO` (`ig_user_id` "me") for the end card, so a renamed account needs no code change; a failed lookup leaves the handle off the card and the post goes ahead.

Music comes only from `assets/audio/catalog.json`: Mixkit tracks under the Mixkit Stock Music Free License, which covers social media video posts with no attribution. Never register these tracks with a rights-management service such as Content ID (the license forbids it), never remix them into a music-only track, and never commit or otherwise redistribute the files; the repository is public. To add or replace a track, download it from its Mixkit listing, record its title, artist, listing page, direct download URL, duration and sha256 in the catalog, run `uv run --frozen python scripts/fetch_audio_catalog.py`, and check the result with the sample renderer. Changing the catalog or the script changes the workflow cache key, so the next run downloads afresh.

Narration reads the validated scene's on-screen text aloud, one line per beat, with the local Kokoro voice (`src/media/narration.py`). The model files are fetched by `scripts/fetch_voice_model.py` into the gitignored `assets/voice/` (pinned by sha256, cached in both workflows), and the voice runs through `scripts/narrate.py`, a PEP 723 script locked in `scripts/narrate.py.lock` that uv runs on Python 3.13 because kokoro-onnx does not support 3.14. The layouts lengthen each beat to fit its spoken line (with 0.2 s of quiet after it), the mix places each line 0.15 s after its beat starts, a Reel the voice would stretch past 30 seconds is read again faster (at most 1.25x, at most twice), and the music bed sits under the voice and ducks while it speaks. Narration is optional by design: a missing model, a failed environment install, a synthesis error or a failed mix is logged as "SVG Reel without narration (REASON)" and the Reel goes out music-only, without the "Narration: AI-generated voice." caption line. `NARRATION=false` turns it off.

## Durable state

Production uses `data/publication_state.json` on `autopilot-state`, updated with GitHub Contents revision checks. The workflow token needs repository contents-write permission. A failed state write prevents publication. Runtime state contains no credentials. The local backend uses an OS file lock plus atomic replacement.

A slot progresses through `preparing -> publishing -> published`. Preparation failures are `failed` and may retry up to three attempts. A lost response after publishing starts is `uncertain`. A killed process leaves its last durable state: expired preparation may be reclaimed after 60 minutes, but publishing/uncertain is never automatically reclaimed. Ownership tokens prevent a superseded worker from crossing the publish boundary.

Successful records include the provider media ID. Legacy records retain their original slot identity and receive a conservative 20-minute completion margin because their timestamp preceded generation. No media ID is invented for them.

Before writes grow the state, older resolved content metadata is compacted to essential receipts. The latest 30 resolved records keep full editorial detail, and recent scene-history snippets are bounded. Publication/container IDs and unresolved outcomes are not discarded to make space. Expired preparation leases become failed records, including exhausted attempts, so interrupted workers cannot silently disappear.

## Reconciliation

Read the uncertain receipt and inspect the Instagram account. Use workflow_dispatch with its exact `resolve_slot` key and either the confirmed `media_id` or `confirm_not_published`. These options are mutually exclusive in the CLI. Reconciliation does not call Instagram.

For a local ledger:

```bash
uv run --frozen python -m src.main --resolve-slot 'DATE|TIME|PILLAR' --media-id CONFIRMED_ID
uv run --frozen python -m src.main --resolve-slot 'DATE|TIME|PILLAR' --confirm-not-published
```

Use the GitHub workflow to reconcile the deployed ledger. A local default ledger is independent; changing it does not repair production. Never operate the same Instagram account with two independent ledgers.

## Failure interpretation

- A 401/403 before generation means credentials or model/account authorization need attention. A local credential failure does not prove GitHub repository secrets are broken.
- "Composio Instagram connection is EXPIRED" means the Instagram login behind the Composio connected account lapsed (Instagram tokens expire after about 60 days unless refreshed). Every Instagram action then returns HTTP 410. Reconnect Instagram in the Composio dashboard; if Composio issues a new connected-account ID, update the `COMPOSIO_CONNECTED_ACCOUNT_ID` secret. The preflight checks the status before any paid generation, so the run fails red instead of finishing green with nothing posted (what happened from 2026-10-06 to 2026-10-11).
- Cloudinary errors and Instagram 9004 media-download errors concern delivered media. Only explicit invalid-location identifiers trigger a retry without location.
- A final-publication transport failure may hide a successful post. Keep it uncertain until checked.
- Empty or unavailable optional trend sources produce evergreen explainers and comparisons. A myth-vs-fact Reel needs cited source records for its facts ("a myth-vs-fact Reel needs selected source records that state each fact" in the topic step). Stat and timeline Reels need evidence with numbers or dates; without it the topic step fails before any model call rather than inventing figures.
- "Model output failed validation; repair call N of 2" followed by "Repaired model output still failed validation" names the problem, for example a number not found in the cited source text. "Salvaged the output by removing what the evidence does not support" means the caption was the only thing left citing such a number and its sentences were dropped. Otherwise that attempt fails before rendering; it is the grounding rule working, not a provider fault.
- "Attempt N of M (PILLAR) failed before publishing (ERROR); trying NEXT next" is the post-is-a-must chain (`src/post_attempts.py`): the same pillar once more with a fresh topic, then `tech-versus`, then `tech-explainer`, each claimed again under the cap, the gap and the window. It stops at once if an attempt reached the publish checkpoint (that receipt is `uncertain`; reconcile it). When every attempt fails the run summary is `failed` with the last slot key.
- "ffmpeg install try N of 3 failed or timed out; retrying" in the install step means the runner's apt mirror stalled; each try is capped at three minutes for `apt-get update` and five for the install.
- SVG Reels are skipped, never replaced by photos, when audio is missing (the music library is downloaded from `assets/audio/catalog.json` at run time; a failed download, logged as "skip TRACK_ID" in the "Download the licensed audio library" step, leaves that theme short, and `ALLOW_SILENT_REELS=true` lets the Reel go out silent instead), when Chrome, `ffmpeg` or `ffprobe` is missing, when a scene does not fit the layout, or when rendering, the ffprobe spec check or the upload fails. The log line "SVG Reel skipped before publishing" carries the reason. The attempt counts against the slot's three-attempt budget.
- "unknown icon 'NAME'" in a validation message means the model named an icon outside the vendored Lucide set; the repair call gets the message, and icons are optional, so the repaired scene may simply omit it.
- For the unused Luma format, empty audio manifests, missing ffmpeg, invalid audio assets, S3 retrieval failures and video preparation failures still fall back to a carousel before publication. Publisher failures never trigger any fallback.
- "this restates a recent post (...)" in a topic validation message means the chosen topic reuses most of a recent topic's words; the repair call picks another subject. "Value should have at most N" names a field over its character cap; the repair is asked for about 10 characters under it.
- "SVG Reel without narration (...)" is informational: the post still goes out, music-only. "voice model missing" means the voice-model cache and download both missed; the next run retries the download.
- "is a greeting", "opens on filler", "is a preamble" or "asks for attention" in a validation message names a weak hook; "the caption's first line is N characters" names a first line too long for the feed preview; "gives away N" means a stat Reel's headline or caption first line states its own figure, which the count-up should reveal. All get the one repair call.
- "Narrated Reel would run N s; reading again at X" is informational: the voice is read again faster (at most 1.25x, at most twice) so the Reel stays near 30 seconds.
- Exhausted generation retries fail the run, bounding additional paid work for that slot.

## Deployment and validation

Merge the code and workflow together. The first main-branch run creates the state branch and migrates existing topic history. Keep that branch and its unresolved records across deployments. The pipeline no longer commits history into main at the end of each run.

Unit and integration-style tests mock external boundaries; run them with the committed lock. A local dry-run makes paid text calls, renders with the local Chrome and `ffmpeg`, and saves `01.mp4`, `reel.svg`, `scene.json` and `caption.json` under `output/dry-run/`, but never uploads, publishes, or updates publication/topic/audio history. Inspect the frames and check each number in `scene.json` against its source record before rolling out a different prompt strategy.

The CI jobs "SVG Reel sample render (NAME)", one per sample in parallel (five narrated Reels in one job took about 19 minutes and hit the 20-minute limit on 2026-10-21), render the fixed scenes in `scripts/samples/svg_reel_scenes.json` with the Ubuntu runner's Chrome and fonts, and "SVG Reel sample artifact" merges their uploads into the `svg-reel-sample` artifact, one folder per sample: one MP4 per pillar in its sample look (steps-cicd, stat-big-number, timeline-hubble), with music baked in when the audio library restored or downloaded, four frames of each (hook entrance, middle, cover frame, end card), a cover still of every sample in every look, and `probe.json` with each MP4's ffprobe summary, look, cover offset, audio track and render time. Check it after changing layouts, looks or the font stack; Linux falls back to Liberation Sans or DejaVu Sans, which the text-fitting widths already assume. Validate changed layouts with the svg-forge plugin's `skills/animated-svg/scripts/validate_svg.py FILE --strict-contrast --theme dark` (0 errors).

The image and Composio contracts are documented in `tests/publishing/SCHEMA.md`. Supported schemas and credentials can change independently of the application. A green local test suite is not proof of live publication.

Optional audio-history and place caches are restored between workflow ticks, and the licensed music library is restored from a cache keyed on `assets/audio/catalog.json` and `scripts/fetch_audio_catalog.py`. They are convenience caches, not the source of publication truth. Generated assets accumulate in Cloudinary; review storage usage and retention rather than deleting live assets automatically.
