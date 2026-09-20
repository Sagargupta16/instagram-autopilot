"""Bridge the existing topic history into the durable ledger without losing old posts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.content import dedup
from src.state.ledger import Ledger
from src.state.store import update


def sync_history(ledger: Ledger) -> None:
    local = dedup._load_raw()

    def seed(data: dict[str, Any]) -> None:
        if data.get("history_migrated"):
            return
        data["history"] = local[-100:]
        for item in local:
            key = item.get("slot_key")
            if not key or key in data["slots"]:
                continue
            try:
                timestamp = datetime.fromisoformat(item["ts"])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
            except (KeyError, ValueError):
                timestamp = datetime.fromisoformat(key[:10]).replace(hour=23, minute=59, tzinfo=UTC)
            # Old timestamps precede generation: allow a conservative completion margin.
            data["slots"][key] = {
                "status": "published",
                "owner": "legacy",
                "topic": item.get("topic", ""),
                "started_at": timestamp.isoformat(),
                "published_at": (timestamp + timedelta(minutes=20)).isoformat(),
                "legacy_receipt": True,
            }
        data["history_migrated"] = True

    update(ledger.store, seed)
    merged = {(item.get("topic"), item.get("ts")): item for item in local}
    for item in ledger.snapshot()["history"]:
        merged.setdefault((item.get("topic"), item.get("ts")), item)
    history = sorted(merged.values(), key=lambda item: item.get("ts", ""))
    if history != local:
        dedup._atomic_write(history)
