"""Bound content metadata without discarding publication evidence."""

from __future__ import annotations

from typing import Any

FULL_CONTENT_RECEIPTS = 30
RECEIPT_FIELDS = {
    "status",
    "owner",
    "started_at",
    "published_at",
    "publish_started_at",
    "updated_at",
    "attempts",
    "container_id",
    "media_id",
    "resolved_at",
    "error",
    "legacy_receipt",
    "topic",
}


def compact(data: dict[str, Any]) -> None:
    """Keep recent editorial detail, minimal older receipts, and all unresolved records."""
    data["history"] = [
        {
            **entry,
            "image_prompts": [prompt[:400] for prompt in entry.get("image_prompts", [])],
        }
        for entry in data["history"][-100:]
    ]
    resolved = sorted(
        (
            (key, entry)
            for key, entry in data["slots"].items()
            if entry["status"] in {"published", "failed"}
        ),
        key=lambda item: item[1].get("started_at", ""),
        reverse=True,
    )
    for key, entry in resolved[FULL_CONTENT_RECEIPTS:]:
        data["slots"][key] = {
            field: value for field, value in entry.items() if field in RECEIPT_FIELDS
        }
