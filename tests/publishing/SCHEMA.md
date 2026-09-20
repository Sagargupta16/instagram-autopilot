# Composio publishing schema evidence

Read-only source inspected 2026-09-20:
<https://docs.composio.dev/toolkits/instagram>.
The page embeds tool-specific `input_parameters` and `output_parameters`.
No credentials, model calls, or tool executions were used for verification.

- `INSTAGRAM_CREATE_MEDIA_CONTAINER` accepts optional `alt_text` (string)
  for a single image or an image carousel child, at most 1,000 characters.
  It is unsupported for videos, Reels, Stories, or carousel parents.
- `INSTAGRAM_CREATE_POST` accepts required `ig_user_id` and `creation_id`
  (strings), plus optional `graph_api_version`. **It does not list
  `max_wait_seconds` or `poll_interval_seconds`.** Its description mentions
  internal retry for not-ready containers; our client never retries publication.
- `INSTAGRAM_GET_POST_STATUS` accepts required `creation_id` (string), plus
  optional `graph_api_version`. Its documented readiness state is `FINISHED`;
  all carousel children must be ready before publishing the parent.
- `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH`, the newer final publishing action,
  accepts `max_wait_seconds` and `poll_interval_seconds`. It is also excluded
  from our retry allowlist, even though the publishers retain the legacy action.
- The response envelope has required boolean `successful`, required `data`,
  and optional `error`. IDs are required nonempty strings at publishing boundaries.

These are public schema observations, not a live publication or connected-account
compatibility test. The legacy actions are currently marked deprecated.

The caller owns durable storage: `before_publish(parent_creation_id)` must
persist `publishing` before returning. Exceptions propagate unchanged from this
callback and no final request is made if it raises. Any error after that boundary
must leave the attempt uncertain until reconciled; do not fall back or replay.
