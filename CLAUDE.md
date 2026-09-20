# CLAUDE.md

> This file stacks on the workspace guidance at `C:\Code\GitHub\AGENTS.md`, its `MEMORY.md` and `STATUS.md`. The guidance below adds repository-specific contracts.

## Project

Headless Python Instagram publisher. Six lifestyle pillars currently produce five-image carousels through Bedrock, Cloudinary, and Composio. Reels remain optional. See README.md and docs/operations.md for current behavior; older docs/plans and CHANGELOG entries are historical.

## Validation

- `uv sync --frozen`
- `uv run --frozen ruff check src tests scripts`
- `uv run --frozen ruff format --check src tests scripts`
- `uv run --frozen pytest --cov=src --cov-branch`
- `uv run --frozen python -m src.main --dry-run` is paid local generation, never upload/publication/history mutation.
- `python -m src.main` is a live publishing command, not a test.

Tests use dummy credentials, disable dotenv, and block sockets. CI exercises Python 3.12 and 3.14 and enforces failures.

## Boundaries

- `adapters/`: low-level service calls.
- `content/`: category-relevant evidence, topic selection, validated content. Preserve the legacy string topic wrapper; the orchestrator uses `generate_topic_brief` and passes its sources into captions.
- `media/`: asset generation, JPEG normalization, S3 retrieval, and audio.
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
7. Content responses require exactly five prompts and aligned alt texts before image work. Preserve source metadata from adapters rather than accepting model-authored source URLs.
8. Diffusion exclusions belong in `negative_prompt`. Retain the anti-illustration/CGI/typography guards and randomized seeds.
9. All published images are validated RGB 1080x1350 JPEGs below 8 MB. Validate actual delivered bytes; a trusted hostname alone does not prove compatibility.
10. Filtered-slide removal must keep alt texts aligned. Dry-run must fail when fewer than two carousel slides survive.
11. Bedrock uses bearer-token requests. Botocore is exclusively for authenticated S3 retrieval, not a replacement for Bedrock authentication.
12. Missing licensed local audio must be detected before paid video generation. Preserve required attribution; never mutate audio history in dry-run.
13. Topic attempts and confirmed publications are different records. Preserve legacy history and unresolved receipts. Do not invent media IDs during migration.
14. Keep `uv.lock` authoritative; `requirements.txt` is a generated runtime-only export. Never disable failing tests or hide their exit status.

## Conventions

Type hints, pathlib, small modules, explicit contracts. Target under 200 lines per module; hard limit 300. Tests mirror source areas. No credentials in logs, state, artifacts, or commits. The existing untracked audio-download script belongs to the user; do not overwrite it.
