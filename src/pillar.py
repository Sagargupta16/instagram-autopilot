"""Content strategy loader: pillars + persona + model IDs from config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict[str, Any]:
    """Read config.json (pillars + persona + cadence + model routing)."""
    return json.loads(CONFIG_PATH.read_text())
