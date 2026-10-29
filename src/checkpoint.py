"""The callback every publication passes right before Instagram's final publish call: it refuses
once the posting window or the slot's date has passed and durably records `publishing`, so an
ambiguous outcome is reconciled instead of retried (contracts 1 and 2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from src.state.ledger import Ledger


def guard(
    config: dict[str, Any], ledger: Ledger | None, key: str, clock: Callable[[], datetime]
) -> Callable[[str], None]:
    def before_publish(container_id: str) -> None:
        instant = clock().astimezone(UTC)
        window = config["cadence"]["window_utc"]
        if not window["start"] <= instant.strftime("%H:%M") < window["end"] or not key.startswith(
            instant.date().isoformat()
        ):
            raise RuntimeError("Posting window ended during generation; slot was not published")
        if ledger is None:
            raise RuntimeError("Publication requires a durable ledger")
        ledger.before_publish(key, container_id, instant)

    return before_publish
