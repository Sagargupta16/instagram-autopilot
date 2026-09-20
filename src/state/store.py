"""Storage contract shared by local and GitHub state backends."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol

from src.state.retention import compact


class ConflictError(RuntimeError):
    """Another writer changed the state since it was read."""


def empty_state() -> dict[str, Any]:
    return {"version": 1, "slots": {}, "history": []}


def validate_state(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported or corrupt publication state")
    if not isinstance(data.get("slots"), dict) or not isinstance(data.get("history"), list):
        raise ValueError("Corrupt publication state: slots/history")
    statuses = {"preparing", "publishing", "published", "failed", "uncertain"}
    for entry in data["slots"].values():
        if not isinstance(entry, dict) or entry.get("status") not in statuses:
            raise ValueError("Corrupt publication state: slot status")
    return data


class Store(Protocol):
    def read(self) -> tuple[dict[str, Any], str | None]: ...

    def save(self, data: dict[str, Any], revision: str | None) -> None: ...


def update[T](store: Store, mutate: Callable[[dict[str, Any]], T]) -> T:
    """Retry only CAS conflicts; a failed durable write must prevent publishing."""
    for _ in range(5):
        data, revision = store.read()
        validate_state(data)
        before = deepcopy(data)
        result = mutate(data)
        compact(data)
        if data == before:
            return result
        try:
            store.save(data, revision)
            return result
        except ConflictError:
            continue
    raise ConflictError("Publication state kept changing; retry on the next scheduler tick")
