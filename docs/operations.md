# Operating the publisher

The scheduler wakes every 20 minutes within the configured UTC window. GitHub cron is best-effort, so planned times are eligibility thresholds, not precise appointments. Only one slot can publish per tick, and the ledger enforces spacing from the last confirmed publication. The plan reserves 40 minutes at the end for polling and generation.

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
- Cloudinary errors and Instagram 9004 media-download errors concern delivered media. Only explicit invalid-location identifiers trigger a retry without location.
- A final-publication transport failure may hide a successful post. Keep it uncertain until checked.
- Empty or unavailable optional trend sources produce evergreen content. They do not justify fabricated current events or statistics.
- Empty audio manifests, missing ffmpeg, invalid audio assets, S3 retrieval failures, and video preparation failures fall back before publication. Publisher failures never trigger a carousel fallback.
- Exhausted generation retries fail the run, bounding additional paid work for that slot.

## Deployment and validation

Merge the code and workflow together. The next eligible main-branch tick creates the state branch and migrates existing topic history. Keep that branch and its unresolved records across deployments. The pipeline no longer commits history into main at the end of each run.

Unit and integration-style tests mock external boundaries; run them with the committed lock. A local dry-run makes paid generation calls and saves preview JPEGs/captions under `output/dry-run/`, but never uploads, publishes, or updates publication/topic/audio history. Inspect images and claims before rolling out a different prompt strategy.

The image and Composio contracts are documented in `tests/publishing/SCHEMA.md`. Supported schemas and credentials can change independently of the application. A green local test suite is not proof of live publication.

Optional audio and place caches are restored between workflow ticks. They are convenience caches, not the source of publication truth. Generated assets accumulate in Cloudinary; review storage usage and retention rather than deleting live assets automatically.
