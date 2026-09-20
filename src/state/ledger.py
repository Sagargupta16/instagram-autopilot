"""Slot ownership and publication receipts, independent of the storage provider."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from src.state.store import Store, update

LEASE_MINUTES = 60
MAX_ATTEMPTS = 3


class Ledger:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.owner = uuid4().hex

    def snapshot(self) -> dict[str, Any]:
        return self.store.read()[0]

    def get(self, key: str) -> dict[str, Any]:
        return self.snapshot()["slots"].get(key, {})

    def claim(
        self, key: str, now: datetime, *, min_gap_minutes: int, max_posts_per_day: int = 2
    ) -> bool:
        def mutate(data: dict[str, Any]) -> bool:
            self._expire_preparation(data, now)
            self._prune(data, now)
            slots = data["slots"]
            existing = slots.get(key, {})
            if existing.get("status") in {"published", "publishing", "uncertain"}:
                return False
            if existing.get("attempts", 0) >= MAX_ATTEMPTS:
                return False
            daily_count = sum(
                entry["status"] == "published" and slot_key.startswith(now.date().isoformat())
                for slot_key, entry in slots.items()
            )
            if daily_count >= max_posts_per_day:
                return False
            for entry in slots.values():
                status = entry["status"]
                if status in {"publishing", "uncertain"}:
                    return False
                if status == "preparing" and datetime.fromisoformat(entry["lease_until"]) > now:
                    return False
                if status == "published":
                    published = datetime.fromisoformat(entry["published_at"])
                    if now - published < timedelta(minutes=min_gap_minutes):
                        return False
            slots[key] = {
                "status": "preparing",
                "owner": self.owner,
                "started_at": now.isoformat(),
                "lease_until": (now + timedelta(minutes=LEASE_MINUTES)).isoformat(),
                "attempts": existing.get("attempts", 0) + 1,
            }
            return True

        return update(self.store, mutate)

    @staticmethod
    def _expire_preparation(data: dict[str, Any], now: datetime) -> None:
        for entry in data["slots"].values():
            if (
                entry["status"] == "preparing"
                and datetime.fromisoformat(entry["lease_until"]) <= now
            ):
                entry.update(
                    status="failed", error="Preparation lease expired", updated_at=now.isoformat()
                )

    def _owned(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        entry = data["slots"].get(key, {})
        if entry.get("owner") != self.owner:
            raise RuntimeError("Publication ownership changed; aborting stale worker")
        return entry

    def remember(self, key: str, topic: str, content: dict[str, Any], now: datetime) -> None:
        def mutate(data: dict[str, Any]) -> None:
            entry = self._owned(data, key)
            entry.update(
                topic=topic,
                caption=content["caption"] + "\n\n" + content.get("hashtags", ""),
                sources=content.get("sources", []),
                alt_texts=content.get("alt_texts", []),
            )
            data["history"].append(
                {
                    "topic": topic,
                    "image_prompts": [p[:400] for p in content["image_prompts"]],
                    "ts": now.isoformat(),
                }
            )
            data["history"] = data["history"][-100:]

        update(self.store, mutate)

    def before_publish(self, key: str, container_id: str, now: datetime) -> None:
        if not container_id:
            raise ValueError("A container ID is required before publishing")

        def mutate(data: dict[str, Any]) -> None:
            entry = self._owned(data, key)
            if (
                entry["status"] != "preparing"
                or datetime.fromisoformat(entry["lease_until"]) <= now
            ):
                raise RuntimeError(
                    "Publication ownership lease expired or publishing already started"
                )
            entry.update(
                status="publishing", container_id=container_id, publish_started_at=now.isoformat()
            )

        update(self.store, mutate)

    def complete(self, key: str, media_id: str, now: datetime) -> None:
        if not isinstance(media_id, str) or not media_id.strip():
            raise ValueError("A confirmed media ID is required")

        def mutate(data: dict[str, Any]) -> None:
            entry = self._owned(data, key)
            if entry["status"] != "publishing":
                raise RuntimeError("Publication was not durably started")
            entry.update(status="published", media_id=media_id, published_at=now.isoformat())
            self._prune(data, now)

        update(self.store, mutate)

    def fail(self, key: str, error: str, now: datetime) -> None:
        def mutate(data: dict[str, Any]) -> None:
            entry = self._owned(data, key)
            if entry["status"] == "published":
                return
            status = "uncertain" if entry["status"] in {"publishing", "uncertain"} else "failed"
            entry.update(status=status, error=error[:500], updated_at=now.isoformat())

        update(self.store, mutate)

    def resolve(self, key: str, *, media_id: str | None, now: datetime) -> None:
        """Operator reconciliation after checking Instagram; never posts anything."""
        if media_id is not None and not media_id.strip():
            raise ValueError("A confirmed media ID cannot be blank")

        def mutate(data: dict[str, Any]) -> None:
            entry = data["slots"].get(key, {})
            if entry.get("status") not in {"publishing", "uncertain"}:
                raise ValueError("Only an uncertain publication can be reconciled")
            entry.update(updated_at=now.isoformat(), resolved_at=now.isoformat())
            if media_id:
                entry.update(status="published", media_id=media_id, published_at=now.isoformat())
            else:
                entry.update(status="failed", error="Operator confirmed no publication")

        update(self.store, mutate)

    @staticmethod
    def _prune(data: dict[str, Any], now: datetime) -> None:
        cutoff = (now - timedelta(days=90)).isoformat()
        data["slots"] = {
            key: value
            for key, value in data["slots"].items()
            if value["status"] not in {"published", "failed"}
            or value.get("started_at", "") >= cutoff
        }
