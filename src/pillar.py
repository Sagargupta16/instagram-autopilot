"""Content strategy loader: pillars, persona, model IDs from config.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict[str, Any]:
    """Read config.json (pillars + persona + model routing)."""
    return json.loads(CONFIG_PATH.read_text())


def get_todays_pillar(config: dict[str, Any]) -> dict[str, Any] | None:
    """Return the pillar scheduled for today (by UTC weekday), or None."""
    today = datetime.now(UTC).strftime("%A").lower()
    for pillar in config["pillars"]:
        if today in pillar["days"]:
            return pillar
    return None
