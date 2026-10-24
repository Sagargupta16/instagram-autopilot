# Changelog

## [0.14.2] - 2026-10-24

### Security
- filelock 3.32.7 -> 4.2.4 (`>=4.2.1,<5`), which fixes GHSA-v4x8-3wr5-3wq8 (high), GHSA-567q-5qvw-pf92 and GHSA-9vhv-jxww-xfm5 (low). All three are in `ReadWriteLock` and `SoftFileLock`; the local state store only uses `FileLock(path, timeout=10)`, whose API 4.0 kept. The Renovate update pinned 4.2.1 in `requirements.txt` while `uv.lock` resolved 4.2.4, so CI's export check failed; both now say 4.2.4.

## [0.14.1] - 2026-10-24

### Security
- certifi 2026.7.22 -> 2026.10.23 (GHSA-6q48-6c7w-9gw2, critical, fixed from 2026.10.19): the new bundle drops the emSign root CAs whose intermediate keys were compromised. The Renovate update moved only `requirements.txt`, so CI's export check failed; `uv.lock` and `requirements.txt` now lock the same version.

## [0.14.0] - 2026-10-24

### Added
- 3D motion in every Reel, all SMIL and deterministic. Behind each scene a perspective floor glides toward the viewer without a seam (its lines are spaced and weighted by one ratio, so a zoom by that ratio lands each line on the next) and wireframe cubes float up in three parallax layers, the near two turning in 3D through a quarter-turn loop (`src/media/svg_depth.py`; decoration under 50% opacity, the dot lattice now stops at the floor's horizon). Cards swing in on a hinge, the takeaway and end card included; icon tiles get a coin-thick base and lift while active; the big number extrudes toward the viewer in eight `accent_text` layers when its count-up lands; the ring tilts up from lying flat with a solid edge; bars grow as boxy solids with a lit top face and a shaded end face; the line draws as a ribbon over a set-back copy; and a myth card turns over on its fact beat (`src/media/svg_solid.py`, `src/media/reel_svg_charts.py`). Only shapes turn: text is never squashed or scaled down, and a test checks it. The 54 sample SVGs (9 samples, 3 looks, with and without a handle) pass the svg-forge validator with 0 errors at 43 to 61 KB.
- "create one": posting is on demand. The workflow (now "Instagram Post") has no cron schedule, its `pillar` input is a choice of the five pillars and `post_now` defaults to on; the daily cap, the 180-minute gap and the 04:00-20:00 UTC window still refuse with a reason. CLAUDE.md gives the procedure a session follows when asked to create one, and README shows the `gh workflow run` command.

### Changed
- The first second shows the subject. The stat visual starts at 0.4 s under the headline instead of 2 s (the number is already counting at 0.9 s), and the first step, milestone, versus row or myth card swings in at 0.7 s while the hook is still read; versus column heads arrive at 0.2 and 0.45 s. Narration beats are unchanged. On the account's first 14 Reels 80.4% of views (weighted) left within three seconds and the median watch was 3.1 s, with the opening frame mostly empty (Instagram insights, read 2026-10-24).
- Reels run 15 to 30 seconds. Every layout has a 15 s floor (stat Reels had 12 s). Narration pauses are shorter (0.15 s before a line, 0.2 s after, from 0.25 and 0.35), and a voice that would push a Reel past 30 s is read again faster, at most 1.25x and at most twice (`narration.fitted`). Measured on the samples: steps 25.2 s, stat 15.0 s, timeline 30.1 s, myths 30.1 s at 1.20x, and versus 31.4 s at the 1.25x ceiling, since Kokoro's speed control saves less than its factor.
- A stat Reel's headline and caption first line may no longer contain its figure (`content/hooks.py`, one repair call), and the stat and caption prompts ask for an opening that names the subject and leaves the answer to the Reel. The three stat Reels that opened on their figure lost 87.5 to 100% of viewers in the first three seconds.
- The pipeline diagram shows the on-demand trigger ("create one") and the 30 s narration cap; `orrery verify` finds all 53 evidence entries and the review scores 94.3 at 880 px.

## [0.13.2] - 2026-10-24

### Changed
- Redrew the pipeline diagram with orrery 0.12.0, which draws icons at 64 px instead of 48. The eight evidence sources go from 32 px (`size: sm`) to 48 px (`size: md`), so their logos read at the README's 880 px instead of shrinking to half the other tiles, and `layout.spacing: compact` keeps the figure at 1174x1562 (it was 1205x1594). Nodes, edges and evidence are unchanged.

## [0.13.1] - 2026-10-21

### Added
- The README's Architecture section shows the pipeline as a diagram (dark and light SVG) in place of the ASCII arrow chain: the scheduled workflow, the slot claim on the `autopilot-state` branch, the eight evidence sources, the Bedrock topic and scene calls, the grounding gate, the SVG, Chrome, ffmpeg and ffprobe render steps with the optional Kokoro narration, and the Cloudinary upload and Composio publish with the checkpoint written first. The spec is `docs/diagrams/pipeline.yaml` (made with orrery), and every node and edge in it carries the file and line it comes from.

## [0.13.0] - 2026-10-21

### Changed
- The Reel end card no longer hard-codes `@creativity.prompt`. `publishing/account.py` reads the connected account's username live (a read-only `INSTAGRAM_GET_USER_INFO` call, `ig_user_id` "me") each time a Reel is drawn, so a rename shows up on the next Reel with no code change. A failed lookup or an unusable username leaves the card with the follow line alone, never a stale name, and never fails the slot. A long username steps down from 56 to 48 or 40 px and is dropped if it still does not fit on one line.
- The follow line reads "Follow for more facts" instead of "Follow for daily explainers": the account posts on most days, not every day, and covers stats, timelines, comparisons and myths as well as explainers.

### Fixed
- The CI "SVG Reel sample render" job hit its 20-minute limit: since narration, the five samples run 15 to 38 s each and rendered one after another in about 19 minutes (218, 120, 243, 287 and 254 s on 2026-10-21). Each sample now renders in its own parallel job (`--name NAME`; the new `--no-stills` flag leaves the cover-still gallery to the stat job), and a final job merges the uploads into the same `svg-reel-sample` artifact, one folder per sample.

## [0.12.1] - 2026-10-20

### Fixed
- Nothing posted on 2026-10-19: its only slot (cool-stats) failed both attempts. The second failure was a 77-character takeaway "repaired" to 71 against a 70 cap. Every scene prompt now gives an "ideally under" target about 10 characters below each hard limit, the caption rules say one character over fails the post, and a repair after a too-long field asks for about 10 characters under its limit (only then; other repairs are unchanged).
- The first 2026-10-19 attempt restated the 2026-10-16 post ("One in four new cars sold worldwide in 2025 was electric" against "1 in 4 ..."), which the exact-wording check missed. `content/novelty.py` now refuses a topic whose content words overlap a recent one by 75% or more (the repair call then picks a different subject). On the last 100 real topics no pair reaches 0.7, and the EV restatement scores 1.0.

## [0.12.0] - 2026-10-18

### Changed
- A ghost layer, the change the portfolio-react covers credit most: every step, versus row and myth card has a waiting panel (3% fill, 10% hairline) from the first frame, and every step connector and timeline node and rail has a waiting outline. Each beat lights its panel up on top, so the opening frame is already a composition rather than a hook over empty space, and the panels still to come stay legible below the active one. The ghosts are static, so they add no animated elements.
- One focal wash: a soft radial glow in the look's accent, 12% at its centre behind the hook, fading out. It is the only `url()` reference in a Reel and points at an internal `kr-` gradient; the inert-SVG test now allows exactly that. Worst-case text contrast on the brightest point of the wash under a ghost panel is 7.7:1 (needs 4.5) and marks 5.3:1 (needs 3), across all three looks.
- The takeaway card gets a 10% hairline border, matching the ghost panels.

## [0.11.2] - 2026-10-18

### Fixed
- The stat value pattern in `reel_svg_count.py` keeps digits, commas and dots out of its currency and suffix groups, so matching stays linear (SonarCloud S8786). It matches every schema-valid stat value exactly as before (20,016 inputs compared).

## [0.11.1] - 2026-10-18

### Fixed
- "the source" in ordinary tech text ("the source system sends a POST") no longer counts as commentary about the evidence. The rule had failed the 2026-10-18 tech-explainer slot twice (a webhook explainer; the repair kept the phrase because it was correct). It now flags the source only when the text says what it reports or leaves out ("the source says", "the source does not give"); article, record, excerpt, snippet and evidence stay as before.

## [0.11.0] - 2026-10-18

### Added
- Two new SVG Reel formats and pillars. `tech-versus` ("X vs Y", `src/media/reel_svg_versus.py`) compares two named things with optional icons on 3 or 4 aspects in rows; each row lights up in turn and its right-hand cell arrives when the narrator reaches it. `myth-vs-fact` (`src/media/reel_svg_myths.py`) shows 2 or 3 common beliefs: each is labelled MYTH, struck through on its fact beat, and FACT appears beneath it, so the final frame shows every myth crossed out above its fact. Myth Reels need cited source records (the topic step refuses an empty selection) and narrate each myth and fact as two lines so the strike lands on the word "Fact". Both get their own topic and scene prompts, kickers in all three looks and sample scenes; pillar weights are now 1.0, 1.5, 0.8, 1.0 and 1.0.

### Changed
- Smaller type on the owner's ask: one scale in `svg_kit.py` (hook 68-76 px, labels 44-48, details 32-34, takeaway 42-44, nothing under 32), down about 14% from 80-88, 52-56, 36-40 and 48-50. Contract 16's floors and their tests follow it; three layout-overflow tests use wider text to keep checking the same fallbacks.
- Design lessons from the portfolio-react cover scenes: a faint dot lattice (6% opacity, one static path, no references) sits behind every scene for depth, line draws and bar growth use an even travel easing (`0.45 0 0.25 1`) while entrances keep the ease-out, and the myth strike is a dash draw rather than a width animation.
- The source line under the takeaway is one helper (`svg_parts.source`) instead of three copies, and the count-up helpers moved to `src/media/reel_svg_count.py`, which brings `reel_svg_stats.py` back under the 300-line limit.
- The prompts tell the model never to count myths or rows in the hook or caption ("3 space myths"), since every number word is checked against the evidence, and to keep cells short because the narrator reads each one.

## [0.10.0] - 2026-10-18

### Added
- Voice-over for every SVG Reel. A local Kokoro voice (kokoro-onnx 0.6.1, Apache-2.0 weights `kokoro-v1.0.fp16.onnx` and `voices-v1.0.bin`, pinned by sha256) reads the validated scene's own on-screen text, one line per beat: the hook, each step, milestone or stat line, and the takeaway. It runs in `scripts/narrate.py`, a PEP 723 script locked in `scripts/narrate.py.lock` that uv runs on Python 3.13, because kokoro-onnx does not support the publisher's 3.14. `scripts/fetch_voice_model.py` downloads the model into the gitignored `assets/voice/`; both workflows cache it and pre-install the environment, and a failure at any step never fails a run.
- The layouts lengthen a beat to fit its spoken line and never shorten one. A narrated steps sample runs 27.05 s instead of 18.8 s, each spoken line starts within 80 ms of its planned beat, and the voice finishes before the cover frame and the end card. A chart's unit is said once, not after every value. Without narration every SVG, duration and cover frame is byte-identical to 0.9.2 (all 21 sample and look combinations compared).
- `audio_bake.mix` places each voice clip at its beat, normalizes the speech to -16 LUFS (-1.5 dBTP), and ducks the music bed under it with a sidechain compressor (measured 4 to 7 dB under speech). Captions of narrated Reels end with "Narration: AI-generated voice."; a Reel whose narration fails goes out music-only without that line. The text sent to the voice (never the screen) reads "$3.4 billion" as "3.4 billion dollars", "1946" as "nineteen forty-six", "Apr" as "April" and "CI/CD" without "slash", checked against Kokoro's phonemes.
- A hook check (`content/hooks.py`, after the MIT hook scorer in Jakeschincariol/instagram-agent-skill): the hook or stat headline may not open with a greeting, filler, a video preamble, "stop scrolling", a hashtag or an emoji. Matching is by whole word, so "your" and "solo" pass.
- The caption's first line must be one complete sentence under 125 characters, the part the feed shows before "... more". The scene prompts ask the takeaway to answer the hook so a replay reads as a loop.

### Fixed
- A model response with a sentence before or after its JSON object is parsed instead of spending the repair call; both failures that cost the 2026-10-14 history-timeline slot ("Extra data" and "Expecting value") now parse. Empty or prose-only responses still go to repair.
- The topic history file is written through a file handle, which clears SonarCloud's path-injection alert on `dedup._atomic_write` (it treated the written text as the path). The output is unchanged.

## [0.9.2] - 2026-10-18

### Fixed
- Captions carry at most five hashtags, Instagram's cap on posts and Reels since 2025-12-18. All 16 posts published since 2026-09-20 went out with 7 to 9 because both caption prompts asked for 5 to 10. The prompts now ask for 3 to 5, most relevant first, and the hashtag validator keeps the first five rather than failing the slot or spending a repair call on extras.

## [0.9.1] - 2026-10-11

### Fixed
- Stat Reels no longer draw a ring for a change. A CI dry run filled a ring to 99% for a 99% decline, which reads as 99% remaining. A ring whose context describes a decline, rise, drop or growth is a validation error (one repair call), and the stat prompt says to use `big_number` for changes.
- The caption credit names only the publisher for Google News records. Their `news.google.com/rss/articles/...` links are 250-character redirects, not the article, and are not clickable in a caption anyway.

## [0.9.0] - 2026-10-11

### Added
- Licensed music for every SVG Reel. `assets/audio/catalog.json` lists 15 Mixkit tracks (five each for chill, upbeat and cinematic) with title, artist, listing page, direct download URL, duration and sha256, under the Mixkit Stock Music Free License (social media video posts, no attribution; never register the tracks with a rights-management service). `scripts/fetch_audio_catalog.py` (standard library only) downloads them into the gitignored theme folders, keeps a file only when its hash matches and writes the gitignored `catalog_manifest.json` the audio picker now reads beside the committed manifest. No audio file is committed. The publishing and CI workflows restore the library from a cache keyed on the catalog and the script, fetch it on a miss, and never fail a run on a failed download.
- Icons: 60 vendored Lucide icons (release 1.55.0, ISC with the MIT notice for Feather-derived icons, in `src/media/lucide/`). Steps, milestones and stat headlines take an optional `icon` from that list, validated by the scene schema; an unknown name triggers the one repair call. Step icons are drawn at 96 px or more in the accent color.
- Three looks (midnight blue, violet, amber, from the svg-forge themes) with their own kicker wording and icon tile shape. Each post takes the look after the last published post's, stored on its receipt, so consecutive posts never look the same.
- A progress bar along the top of the safe area that fills over the Reel, and a 2-second end card with `@creativity.prompt` and "Follow for daily explainers" while the scene dims behind it.
- The cover frame: the Reel container now sends `thumb_offset` (milliseconds) half a second into the final hold, so the profile grid shows the complete card, not the opening frame. The value comes from the composer's timeline (`Reel.cover`) and is saved in the dry-run `scene.json`.
- The CI `svg-reel-sample` artifact now holds one MP4 per pillar in a different look, with music baked in when the library is available, four frames of each (hook entrance, middle, cover frame, end card) and a cover still of every sample in every look.

### Changed
- Cadence for a near-zero-follower account: at most two posts per UTC day, at least 180 minutes apart, with `post_probability` `[0.05, 0.35, 0.60]` (it was four posts and 60 minutes). Meta's spam policy names automated high-frequency posting of repetitive content.
- Less text, more picture: a step's detail (now at most 48 characters) shows only while that step is active, its card glows and its icon pops, then the row collapses to icon and label and dims until the takeaway. Timeline events are at most 44 characters on a rail of icon nodes that pop while active. The prompts keep the full explanation in the caption.
- A stronger opening: the hook is readable on the first frame and each word brightens in turn while its line pops (never past the safe area), under the kicker and an underline sweep.
- Steps and timelines hold for 4 seconds (2 with the complete scene, then the end card), so they run 14.4 to 21 seconds.
- `compose()` drops the kicker, then the icons, before a scene counts as not fitting.

### Fixed
- The baked audio fade now ends at the Reel's real length. It used `int(duration)`, which faded out early and left the last fraction of a second silent (0.8 s on an 18.8 s Reel).

## [0.8.2] - 2026-10-11

### Fixed
- SVG Reel scenes and captions may no longer talk about their evidence instead of the subject. A live stat scene put "the summary omits species and baseline details" on the final frame; viewers never see the source records, so that reads as a broken post. `src/content/voice.py` flags summary, article, headline, excerpt, record and "omits / not stated / no details" phrasing in every scene field and the caption, which triggers the one repair call and then fails the slot. Attribution such as "per Chron" and ordinary words such as "open source" pass. The caption and stat prompts say the same.

## [0.8.1] - 2026-10-11

### Fixed
- The Composio preflight now requires the Instagram connected account to be `ACTIVE`. The Instagram token expired on 2026-10-02, Composio marked the connection `EXPIRED` on 2026-10-06, and every run since failed at its first Instagram call with HTTP 410 while the preflight, which only checked that the record existed, kept reporting OK. An inactive connection now fails the run before any paid generation, with "Composio Instagram connection is EXPIRED; reconnect it in Composio before posting".

## [0.8.0] - 2026-10-11

### Added
- Animated SVG Reels as a new `content_format: svg_reel` with three scene kinds: `steps` (how-it-works cards joined by connectors with a travelling packet), `stat` (big-number count-up, up to six ranked bars, a percent ring, or a line that draws in) and `timeline` (four to six dated milestones down a rail). Scenes are 1080x1920 self-contained SMIL SVGs on one clock, 12 to 20 seconds, with every text box checked against the Reels safe area and type sizes from 36 to 88 px.
- `src/media/svg_video.py` renders the SVG with headless Chrome (batches of eight frames tiled in one screenshot, each copy seeked with `setCurrentTime`) and pipes frames to ffmpeg for H.264 High, yuv420p, BT.709, 30 fps, +faststart. `src/media/reel_probe.py` checks the delivered file with ffprobe before upload. Licensed audio is baked with the existing `audio_bake`. No new Python dependency.
- Number grounding (`src/content/grounding.py`): every number, percentage, date and number word in a scene, and in its caption outside links and hashtags, must appear in the adapters' title or excerpt text; stat scenes only in the record they cite. One repair call, then the slot fails before rendering. Source lines on screen and in the caption come from adapter metadata.
- Pillars `tech-explainer` (weight 1.0), `cool-stats` (1.5) and `history-timeline` (0.8), with mixed science, space, sports, world and internet-culture feeds for stats and Wikipedia lead sections as dated evidence for timelines. Google News records keep their publisher.
- `--pillar ID` and the `pillar` workflow input swap the pillar of a slot that is already due. `--post-now` and the `post_now` input (with a pillar) post in the current minute inside the window, refusing with a reason when the daily cap, minimum gap or ledger claim would be broken.
- CI job "SVG Reel sample render" renders `scripts/samples/svg_reel_scenes.json` with real Chrome and ffmpeg on Ubuntu and uploads the `svg-reel-sample` artifact. `scripts/render_svg_reel_sample.py` does the same locally.
- Dry-run previews of SVG Reels save `01.mp4`, `reel.svg` and `scene.json`. Validation logs when the repair call is used and why the repaired output still failed.

### Changed
- The account now publishes SVG Reels only. The six lifestyle photo pillars are replaced; carousel, single-image and Luma Reel code paths remain as unused formats. An SVG Reel that cannot be prepared is skipped, never replaced by a photo carousel.
- Cadence: up to four posts per UTC day with a 60-minute minimum gap; the plan favours three or four posts and leaves about 4% of days empty.
- Persona tone and calls to action rewritten for a clear, visual data and tech account; the default niche is `creative_data_tech`.
- Topic prompts take a per-format brief from `prompts/formats/`; SVG pillars use `prompts/svg_caption.txt` and no longer ask for image prompts.
- The workflow installs ffmpeg for any Reel pillar, reports the runner's Chrome, and passes the `ALLOW_SILENT_REELS` repository variable (default `false`).
- CLAUDE.md contracts 7 to 10 and 12 are scoped to the formats they govern; contracts 15 to 21 cover grounding, the safe area and type floors, contrast, render-before-publish checks, no photo fallback, dry-run and `--post-now`.
- `pyproject.toml`: `0.7.1 -> 0.8.0`.

### Changed (durable publishing, previously unreleased)
- Replace burst publication with short scheduler ticks, actual publication spacing, daily limits, bounded preparation retries, and durable GitHub/local publication receipts.
- Fail runs on publishing errors and quarantine uncertain outcomes instead of blindly republishing.
- Validate generated content and strategy; preserve category-relevant evidence and reject exact repeated topics with one bounded repair.
- Improve carousel direction with a strong cover, coherent five-slide progression, useful takeaways, and aligned alt text.
- Normalize images to validated portrait JPEGs, check delivered bytes, and poll Instagram draft readiness.
- Keep dry-run previews local; validate audio before video generation, fetch private S3 output using IAM, preserve attribution, and stop fallbacks at the publication boundary.
- Enforce lint, formatting, tests, coverage, and frozen dependencies in CI on Python 3.12 and 3.14.
- Refresh setup, recovery, optional Reel requirements, and cost documentation.

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
