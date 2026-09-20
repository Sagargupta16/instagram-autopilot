"""Process-safe local state with atomic replacement."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock

from src.state.store import ConflictError, empty_state, validate_state


class LocalStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> tuple[dict[str, Any], str | None]:
        if not self.path.exists():
            return empty_state(), None
        raw = self.path.read_bytes()
        return validate_state(json.loads(raw)), hashlib.sha256(raw).hexdigest()

    def save(self, data: dict[str, Any], revision: str | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.path) + ".lock", timeout=10):
            _, current = self.read()
            if revision != current:
                raise ConflictError("Local publication state changed")
            encoded = json.dumps(validate_state(data), indent=2, ensure_ascii=False)
            fd, name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                Path(name).replace(self.path)
            finally:
                Path(name).unlink(missing_ok=True)
