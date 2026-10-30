# Instagram Autopilot v2 — Premium Multi-Slot Design Spec

Date: 2026-07-03
Status: Draft, ready for implementation planning

## Summary

Upgrade the daily-post bot from a single AI-niche carousel to a randomized
multi-slot pipeline that publishes 0-3 posts/day across 6 lifestyle categories
(travel/food/fitness/entertainment/tech/lifestyle), with per-topic Meta-Places
location tags, royalty-free ffmpeg-baked audio on every Reel, and per-pillar
photoreal style.

## Non-goals

- Not implementing IG's native trending-audio picker (Graph API cannot). We
  bake CC0 audio into the mp4 instead.
- Not building a Meta Graph passthrough in Composio (upstream missing; we call
  Graph directly for `/pages/search`).
- Not adding Reddit / YouTube-chart / pytrends as trend sources — all
  blocked/broken from GH Actions IPs as of 2026-07-03.
- Not adding a UI or dashboard. Pure headless CI-driven.

## Architecture changes

### adapters/ (one external service per file)

- `src/adapters/places.py` **NEW** — Meta Graph `/pages/search`. Signature:
  `resolve_location_id(query: str) -> str | None`. Filters response to entries
  with populated `location.latitude` AND `location.longitude`. Reads/writes
  `assets/cache/places.json` (30-day TTL). Uses `META_USER_ACCESS_TOKEN`.
- `src/adapters/composio.py` **MODIFY** — Add `location_id: str | None = None`
  passthrough on `execute_action` call sites. Rename slug
  `INSTAGRAM_CREATE_MEDIA_CONTAINER` → `INSTAGRAM_POST_IG_USER_MEDIA` (aliased
  server-side but bump for clarity). Match new error code
  `INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID` on the `error` field.
- `src/adapters/pixabay.py` **NEW** (one-off, not runtime) — used by
  `scripts/curate_audio.py` to scrape MP3 direct-URLs during catalog build.
- `src/adapters/wikipedia.py` **NEW** — pageviews top-1000 for
  `date - 2 days`. Filters `Special:*`, `Main_Page`. UA:
  `InstagramAutopilotBot/1.0 (github.com/Sagargupta16; sg85207@gmail.com)`.
- `src/adapters/google_news.py` **NEW** — `/rss/search?q={cat}` per category,
  2s sleep between calls. Descriptive UA.
- `src/adapters/guardian.py` **NEW** — `content.guardianapis.com/search` with
  `api-key=test` initially, `GUARDIAN_API_KEY` env override for later
  registered key.
- `src/adapters/lemmy.py` **NEW** — `lemmy.world/api/v3/post/list`, per
  community, fallback to `lemmy.ml` on 5xx/timeout.
- `src/adapters/reddit.py` **DELETE** — confirmed still 403 from GH runners.
- Kept as-is: `bedrock.py`, `cloudinary_host.py`, `hackernews.py`,
  `huggingface_papers.py`, `producthunt.py`, `github_trending.py`.

### content/

- `src/content/trends.py` **MODIFY** — extend parallel fan-out to include the
  4 new adapters (wikipedia, google_news, guardian, lemmy). Signature stays
  `fetch_trending_topics() -> list[str]` but now accepts optional
  `category: str | None` to filter/bias results. Per-source try/except stays.
- `src/content/topic.py` **MODIFY** — accept full `pillar` dict; injects
  `{category}` and `{region_hint}` into the prompt. `region_hint` is a
  random pick from `pillar.location.regions` (using the same daily RNG seed
  as `plan_today` for determinism), or empty string if the list is empty.
- `src/content/caption.py` **MODIFY** — parse `location_query` and
  `audio_theme` from Bedrock JSON output. Fall back to `None` and pillar
  default respectively when missing.

### media/

- `src/media/audio_bake.py` **NEW** — single function
  `bake(video: Path, track: Path, duration_s: int) -> Path`. Runs:

  ```
  ffmpeg -i {video} -i {track}
    -map 0:v:0 -map 1:a:0
    -c:v copy
    -c:a aac -b:a 128k -ar 48000 -ac 2
    -af "afade=t=in:st=0:d=0.5,afade=t=out:st={duration_s-0.5}:d=0.5"
    -shortest
    -movflags +faststart
    {video.parent}/{video.stem}-baked.mp4
  ```

  Fade-out offset dynamic per duration. Preflights `shutil.which("ffmpeg")`.
  Raises `AudioBakeError` on non-zero exit; captures stderr.
- `src/media/audio_picker.py` **NEW** — reads
  `assets/audio/audio_manifest.json`, filters by requested theme, excludes
  `track_id`s from `assets/cache/audio_history.json` (last 2 days). Random
  pick from remaining. Appends selected `track_id` + today to history file
  atomically (temp+rename, same pattern as `dedup.py`).
- `src/media/image.py`, `src/media/video.py` — no changes.

### publishing/

- `src/publishing/image_post.py` **MODIFY** — accept `location_id: str |
  None`, pass to container create.
- `src/publishing/reel.py` **MODIFY** — same as above; also confirm baked
  mp4 URL comes from S3 with ≥1h signed TTL.
- `src/publishing/carousel.py` **MODIFY** — critical: `location_id` on the
  PARENT `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` call only, NEVER on child
  containers (`_create_child_container`). Per Meta doc: children reject it.
- All three: retry once without `location_id` if Composio raises
  `INVALID_LOCATION_ID`. Log the fallback.

### flows/

- `src/flows/reel_flow.py` **MODIFY** — insert audio-bake step between
  `generate_video()` and `publish_reel()`: pick track via `audio_picker`,
  download baked mp4 back from S3 (or bake locally if we already staged the
  Luma output), re-upload to S3 with fresh 1h-TTL signed URL, then publish.
- `src/flows/carousel_flow.py`, `image_flow.py` **MODIFY** — accept
  `location_id` from `caption_data`; pass to publisher.

### top-level

- `src/schedule.py` **MODIFY** — replace `apply_jitter(max_minutes)` with
  `plan_today(date, cfg, pillars) -> list[SlotPlan]`. Keep `apply_jitter` as
  internal helper for intra-slot randomization (0-30min around planned time).
- `src/main.py` **MODIFY** — top of `run()`: `plan = plan_today(today())`;
  loop slots, `sleep_until_utc(slot.time_utc)`, per-slot preflight, per-slot
  IG-daily-count check (skip if ≥25 published today). Global 3/day cap
  enforced by `plan_today`.
- `src/pillar.py` **MODIFY** — `get_todays_pillar` removed; pillar selection
  moves into `plan_today` (RNG-weighted per slot).
- `src/settings.py` **MODIFY** — add `meta_user_access_token`,
  `meta_graph_api_version: str = "v21.0"`, `guardian_api_key: str = ""`.
- `config.json` **MODIFY** — new schema (below).
- `prompts/topic.txt`, `prompts/caption.txt` **MODIFY** — new placeholders +
  output fields.
- `assets/audio/{chill,upbeat,cinematic}/*.mp3` **NEW** — 30 tracks total.
- `assets/audio/audio_manifest.json` **NEW** — metadata (below).
- `assets/cache/` **NEW** — `places.json`, `audio_history.json`. Gitignore
  initially; graduate to committed like `data/posted_topics.json` if needed.
- `scripts/curate_audio.py` **NEW** — one-off Pixabay scraper.
- `.github/workflows/daily-post.yml` **MODIFY** — `apt-get install -y
  ffmpeg` in setup step; `timeout-minutes: 480`; keep single cron (Python
  sleeps between slots).

## Config schema (config.json)

```json
{
  "persona": {"name": "…", "tone": "…", "cta_styles": ["…"]},
  "cadence": {
    "max_posts_per_day": 3,
    "post_probability": [0.15, 0.35, 0.35, 0.15],
    "window_utc": {"start": "04:00", "end": "20:00"},
    "min_gap_minutes": 90,
    "skip_probability": 0.05
  },
  "categories": ["travel", "food", "fitness", "entertainment", "tech", "lifestyle"],
  "pillars": [
    {
      "id": "travel-cinematic",
      "category": "travel",
      "content_format": "reel",
      "audio_theme": "cinematic",
      "image_style": "Steve McCurry / National Geographic reportage, mid-day natural light, environmental portrait",
      "location": {"regions": ["Bali", "Tokyo", "Lisbon", "Reykjavik", "Kyoto"]},
      "hashtags": ["#travel", "#wanderlust", "#reels", "#worldwide"],
      "weight": 1.5
    },
    {
      "id": "food-editorial",
      "category": "food",
      "content_format": "carousel",
      "audio_theme": "upbeat",
      "image_style": "Peter Menzel table-top editorial, overhead flat-lay, natural window light",
      "location": {"regions": []},
      "hashtags": ["#foodie", "#foodstagram", "#foodphotography"],
      "weight": 1.2
    }
  ],
  "models": {
    "text": "us.anthropic.claude-fable-5",
    "image": "stability.stable-image-ultra-v1:1",
    "video": "luma.ray-v2:0"
  }
}
```

Removed: `niche` (top-level), `content_types` (unused), `posting.time_utc`,
`posting.days`. `pillars[].days` also removed (RNG picks daily).

## Random cadence algorithm

```python
def plan_today(date: date, cfg: Cadence, pillars: list[Pillar]) -> list[SlotPlan]:
    rng = random.Random(int(date.strftime("%Y%m%d")))
    n = min(rng.choices([0, 1, 2, 3], weights=cfg.post_probability)[0], cfg.max_posts_per_day)
    if n == 0:
        return []
    start = to_minutes(cfg.window_utc.start)
    end = to_minutes(cfg.window_utc.end)
    slots: list[int] = []
    for _ in range(50):
        if len(slots) == n:
            break
        cand = rng.randint(start, end)
        if all(abs(cand - s) >= cfg.min_gap_minutes for s in slots):
            slots.append(cand)
    slots.sort()
    weights = [p.weight for p in pillars]
    return [
        SlotPlan(
            time_utc=to_hhmm(m),
            pillar=rng.choices(pillars, weights=weights)[0],
            skip=(rng.random() < cfg.skip_probability),
        )
        for m in slots
    ]
```

Determinism guarantee: same `date` → same plan (safe to re-run after CI
failure). `skip_probability` adds a 5% coin-flip skip per slot so even
deterministic days can drop posts. Post-generation IG-daily-count guard sits
in `main.run()` — if `count_posts_today() >= 25`, stop.

## Prompt template changes

### topic.txt

New template placeholders: `{category}`, `{region_hint}`. Prompt now:

```
Pick a fresh, culturally-current topic within {category}. If {region_hint}
is non-empty, bias the topic toward that region or place. Ground the topic
in the trending signals below (they update daily).
```

### caption.txt

Output JSON extends to:

```json
{
  "caption": "…",
  "hashtags": "#… #…",
  "x_post": "…",
  "image_prompts": ["…", "…", "…", "…", "…"],
  "video_prompt": "…",
  "location_query": "Eiffel Tower, Paris | null",
  "audio_theme": "cinematic"
}
```

- `location_query`: real physical Place searchable via Meta `/pages/search`.
  Set to `null` if the topic has no natural location (e.g. abstract tech).
- `audio_theme`: enum `{chill, upbeat, cinematic, ambient, energetic}`.
  Falls back to `pillar.audio_theme` if missing/invalid.
- Existing `image_prompts` array unchanged in structure; `pillar.image_style`
  injected into the style block replaces the hardcoded photojournalist
  vocabulary (still photoreal, just varies per pillar).

## Assets & licensing

```
assets/audio/
  chill/*.mp3      (10 tracks)
  upbeat/*.mp3     (10 tracks)
  cinematic/*.mp3  (10 tracks)
  audio_manifest.json
```

Manifest entry:
```json
{
  "track_id": "chill-001",
  "filename": "chill/lofi-rain.mp3",
  "theme_tags": ["chill", "ambient"],
  "license": "Pixabay Content License",
  "attribution_required": false,
  "source_url": "https://pixabay.com/music/…",
  "duration_s": 137,
  "curated_at": "2026-07-03"
}
```

Curation (`scripts/curate_audio.py`, one-off, not CI):
- Scrape Pixabay category pages
- Filter: play count < 100k, duration ≥ 60s, upload date ≥ 3 months old
- Download 10 tracks per theme via direct MP3 URL (Pixabay's audio-element
  `src`)
- Write manifest with source URL + license text preserved for future
  Content-ID appeal

Anti-repeat (`assets/cache/audio_history.json`):
```json
{"history": [{"date": "2026-07-03", "track_ids": ["chill-001", "upbeat-004"]}]}
```
`audio_picker.pick(theme)` filters `theme_tags ∋ theme AND track_id NOT IN
history[-2:]`. Atomic-append on selection.

## New env vars / GitHub secrets

- `META_USER_ACCESS_TOKEN` — long-lived (60d) FB user token. Scopes:
  `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`,
  `pages_show_list`. Setup:
  1. Graph API Explorer → generate short-lived user token with above scopes
  2. Exchange for long-lived: `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=…&client_secret=…&fb_exchange_token=…`
  3. Store in GH Actions secrets; document manual re-issue every ~55 days
- `META_GRAPH_API_VERSION` — default `v21.0`.
- `GUARDIAN_API_KEY` — optional; adapter falls back to `test` string when
  empty. Register at `open-platform.theguardian.com/register/` before PR 6.
- No new Composio key.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wide-niche feed drifts stylistically | Per-pillar `image_style` + `audio_theme` keep visual/audio cohesion within each post; RNG weights let travel/tech dominate if desired |
| Composio doesn't expose Meta user token | Store `META_USER_ACCESS_TOKEN` independently in settings |
| `pages_read_engagement` not actually granted at consent | Preflight `GET /me/permissions`, hard-fail before Bedrock spend |
| `/pages/search` may need Page Public Metadata Access Feature (app review) | User token first; on 403, log + publish without location tag |
| `category` field on Page response unverified | Request `fields=id,name,location`; skip `category` for now |
| Places cache staleness (Meta re-IDs Pages?) | 30-day TTL + invalidate on `INVALID_LOCATION_ID` at publish time |
| `/pages/search` per-endpoint rate limit undocumented | Watch `X-Business-Use-Case-Usage` header; cap 20 searches/day |
| IG Content ID false-positive on Pixabay track | Curate <100k-play tracks; store `source_url` per Reel for appeal |
| GH Actions 5-min cron floor | Single-fire cron at 04:00 UTC + Python `sleep_until_utc()` between slots |
| Runner 6h default timeout | Bump to 480min; window is 04:00-20:00 UTC = 16h — split into two workflows if overrun in practice |
| ffmpeg missing on runner | `apt-get install -y ffmpeg`; preflight `shutil.which("ffmpeg")` |
| Pixabay HTML selector drift | One-off scrape at curation; runtime reads local files only |
| Google News RSS rate under load | 2s inter-call sleep, descriptive UA |
| Guardian test-key quota shared | Register free dev key before rollout PR 6 |
| Lemmy.world uptime | Fallback list: `lemmy.ml`, `sh.itjust.works` |
| Composio wraps IG errors in HTTP 200 successful:false | Existing `ComposioActionError`; match `INVALID_LOCATION_ID` on `error` field, not HTTP status |
| Baked mp4 encoding rejected by IG | Codec spec-matched: H.264 stream-copy + AAC-LC 48kHz 128kbps stereo per IG doc |
| Signed S3 URL expires before Meta fetches | 1h TTL minimum on the pre-signed URL |

## Test plan

Every new file gets tests mirroring src/ layout, pytest AAA, one behavior per
test:

- `tests/test_schedule.py`
  - `test_plan_today_deterministic_per_date`
  - `test_plan_today_differs_across_dates`
  - `test_plan_respects_max_posts_per_day` (force RNG rolls of 4)
  - `test_plan_respects_min_gap` (no two slots within 90 min)
  - `test_plan_zero_posts_returns_empty`
- `tests/media/test_audio_bake.py`
  - `test_bake_wraps_mp4_with_track` (ffmpeg on fake tempfiles; ffprobe
    verifies AAC stream + unchanged H.264)
  - `test_bake_fade_offset_5s` and `test_bake_fade_offset_9s`
  - `test_bake_raises_on_missing_ffmpeg` (monkeypatch `shutil.which`)
- `tests/media/test_audio_picker.py`
  - `test_picker_avoids_last_two_days`
  - `test_picker_filters_by_theme`
  - `test_picker_atomic_history_append`
- `tests/adapters/test_places.py`
  - `test_pages_search_picks_first_with_location`
  - `test_pages_search_returns_none_on_empty_data`
  - `test_pages_search_uses_cache_on_second_call`
  - `test_pages_search_falls_back_to_none_on_403`
- `tests/adapters/test_wikipedia.py` — happy path + fallback on 404 for
  date-2.
- `tests/adapters/test_google_news.py` — parses RSS `<item>` correctly.
- `tests/adapters/test_guardian.py` — happy path with `test` key.
- `tests/adapters/test_lemmy.py` — happy path + primary→fallback swap.
- `tests/publishing/test_carousel.py` — add
  `test_location_id_only_on_parent_not_children`.
- `tests/publishing/test_reel.py` (or `test_composio.py`) — add
  `test_retry_without_location_on_invalid_id`.
- `tests/content/test_trends.py` — `test_survives_one_source_failure`.
- `tests/content/test_caption.py` — `test_parses_location_query_and_audio_theme`.

Existing tests continue to pass on each PR.

## Rollout plan

Each PR is independently mergeable, green on CI, and behavior-preserving on
merge (feature flags via config defaults).

1. **PR 1 — Wide-niche trend adapters**: 4 new adapters + `trends.py`
   integration + reddit deletion. No config change; existing pillars still
   route through AI-skewed sources plus new lifestyle ones.
2. **PR 2 — Config schema v2 + cadence RNG**: new `Cadence` model,
   `plan_today()`, `main.run()` slot loop. Ship with `max_posts_per_day: 1`
   → behaves identically to today.
3. **PR 3 — Audio bake**: `curate_audio.py` (run once locally, commit
   `assets/audio/` + manifest), `audio_picker`, `audio_bake`, `reel_flow`
   integration, ffmpeg install in workflow, preflight check.
4. **PR 4 — Places integration**: `places.py` adapter, `caption.txt` new
   fields, publisher `location_id` passthrough + retry-without-location
   fallback. Add `META_USER_ACCESS_TOKEN` secret.
5. **PR 5 — Wide-niche pillars go live**: `config.json` replaced with 6-8
   category pillars, `max_posts_per_day: 3`, `post_probability` weighted for
   1-2 posts/day mode.
6. **PR 6 — Guardian real key + Lemmy fallback instances**: swap `test` key,
   add fallback list. Optional polish.

## Open questions (defer to implementation)

- Cache format for `places.json`: flat `{query: page_id, cached_at}` map or
  namespaced by region? Start flat.
- Should `plan_today` output persist to `data/plan_YYYY-MM-DD.json` for
  observability? Nice-to-have, not required.
- Baked-mp4 S3 key naming: `baked/{yyyy-mm-dd}/{slot}-{track_id}.mp4` for
  audit trail.
