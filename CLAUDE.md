# CLAUDE.md

> This file stacks on the workspace guidance at `C:\Code\GitHub\AGENTS.md`, its `MEMORY.md` and `STATUS.md`. The guidance below adds repository-specific contracts.

## Project

Headless Python Instagram publisher for a creative data and tech account. Three pillars (tech-explainer, cool-stats, history-timeline) produce animated SVG Reels: Bedrock writes a validated, number-grounded scene, `src/media` draws it as a 1080x1920 SMIL SVG, headless Chrome and ffmpeg render it to MP4, and Cloudinary plus Composio publish it. The carousel, single-image and Luma Reel code paths remain supported formats, but no configured pillar uses them. See README.md and docs/operations.md for current behavior; older docs/plans and CHANGELOG entries are historical.

## Validation

- `uv sync --frozen`
- `uv run --frozen ruff check src tests scripts`
- `uv run --frozen ruff format --check src tests scripts`
- `uv run --frozen pytest --cov=src --cov-branch`
- `uv run --frozen python scripts/render_svg_reel_sample.py OUT_DIR` renders the fixed sample scene with real Chrome and ffmpeg (no credentials, no network); CI uploads it as the `svg-reel-sample` artifact.
- `uv run --frozen python -m src.main --dry-run` is paid local generation, never upload/publication/history mutation.
- `python -m src.main` is a live publishing command, not a test.

Tests use dummy credentials, disable dotenv, and block sockets. CI exercises Python 3.12 and 3.14 and enforces failures.

## Boundaries

- `adapters/`: low-level service calls.
- `content/`: category-relevant evidence, topic selection, validated content, SVG scenes (`scenes.py`) and number grounding (`grounding.py`). Preserve the legacy string topic wrapper; the orchestrator uses `generate_topic_brief` and passes its sources into captions.
- `media/`: asset generation, JPEG normalization, S3 retrieval, audio, SVG composition (`svg_kit.py`, `reel_svg*.py`), Chrome and ffmpeg rendering (`svg_video.py`) and ffprobe checks (`reel_probe.py`).
- `slot_rules.py`: forced pillars, on-demand posting refusals and slot times already used.
- `flows/`: compose media and publication; return a confirmed media ID or None for a dry-run.
- `publishing/`: Composio schemas, draft readiness, alt text, final publish callback.
- `state/`: conditional local/GitHub persistence, ownership leases, migration, and receipt transitions.

## Contracts that must survive changes

1. Never make an irreversible publication before `before_publish(container_id)` returns. That callback must persist the publishing state. A callback exception aborts publication.
2. Never blindly retry the final publish call. After its boundary, an ambiguous response requires reconciliation, not a fallback or regenerated post.
3. Do not downgrade confirmed media success because optional audio-history saving failed.
4. At most one due slot per scheduler tick. Enforce actual successful-post spacing and the daily cap through shared state. No multi-hour runner sleeps.
5. GitHub Actions must use the GitHub state backend, not ephemeral local state. The dedicated state branch is not an application deployment branch.
6. Atomic JSON replacement alone is not interprocess protection: keep local file locking and GitHub revision compare-and-swap checks.
7. Photo formats (carousel, image, Luma Reel): content responses require exactly five prompts and aligned alt texts before image work. Preserve source metadata from adapters rather than accepting model-authored source URLs.
8. Photo formats: diffusion exclusions belong in `negative_prompt`. Retain the anti-illustration/CGI/typography guards and randomized seeds.
9. Photo formats: all published images are validated RGB 1080x1350 JPEGs below 8 MB. Validate actual delivered bytes; a trusted hostname alone does not prove compatibility.
10. Carousels: filtered-slide removal must keep alt texts aligned. Dry-run must fail when fewer than two carousel slides survive.
11. Bedrock uses bearer-token requests. Botocore is exclusively for authenticated S3 retrieval, not a replacement for Bedrock authentication.
12. Reels (Luma and SVG): missing licensed local audio must be detected before paid video generation or rendering. Preserve required attribution; never mutate audio history in dry-run.
13. Topic attempts and confirmed publications are different records. Preserve legacy history and unresolved receipts. Do not invent media IDs during migration.
14. Keep `uv.lock` authoritative; `requirements.txt` is a generated runtime-only export. Never disable failing tests or hide their exit status.
15. SVG Reels: every number, percentage, date and number word in a scene, and in its caption outside links and hashtags, must appear in the title or excerpt text the adapters returned for that topic (stat scenes: the cited `source_index` record only), after normalizing thousands separators and units. One repair call, then the slot fails before rendering. Never publish an invented, computed or remembered statistic. Source names shown on screen and in the caption come from adapter metadata, never from model text.
16. SVG Reels: all text stays inside the Reels safe area (x 60-1020, y 250-1600, with the rise margin) at the minimum sizes: hook 80 px bold, step labels 52 px, details 36 px, takeaway 48 px. Fit text with the measured width table in `svg_kit.py` (widest of DejaVu Sans, Liberation Sans and Segoe UI); a scene that does not fit raises `LayoutError` before rendering.
17. SVG Reels: text at least 4.5:1 and marks at least 3:1 on what they sit on (`TEXT_ON` and `MARK_ON` in `svg_kit.py`); SMIL only, self-contained (no scripts, external fonts or images), ids prefixed `kr-`, model text escaped, the hook visible on the first frame. Never add prefers-reduced-motion gating.
18. SVG Reels: render before publish. The renderer refuses blank frames, and the delivered MP4 must pass `reel_probe.verify` (H.264 High, yuv420p, 1080x1920, 30 fps, expected duration, at most 100 MB, an AAC stream exactly when audio was baked) before any upload.
19. SVG Reels only: a failure before the publisher boundary skips the post as a failed attempt (retried on a later tick within the attempt budget). It never falls back to a photo carousel or a Luma video.
20. SVG Reel dry-run renders locally and saves `01.mp4`, `reel.svg` and `scene.json` under `output/dry-run/`; it never uploads, publishes, or writes topic, audio or publication history.
21. `--post-now` (with `--pillar`) is the only exception to the due-slot rule in contract 4: the current minute becomes the one candidate slot for that run so the owner can trigger a test post without waiting for the deterministic plan. It still runs once, inside the posting window, through the ledger claim, daily cap, minimum gap, `before_publish` checkpoint and no-retry rule, and it refuses with a reason when any of them would be broken. `--pillar` alone only swaps the pillar of a slot that is already due.

## Conventions

Type hints, pathlib, small modules, explicit contracts. Target under 200 lines per module; hard limit 300. Tests mirror source areas. No credentials in logs, state, artifacts, or commits. The existing untracked audio-download script belongs to the user; do not overwrite it.
