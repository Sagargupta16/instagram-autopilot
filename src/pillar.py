"""Content strategy loader: pillars + persona + model IDs from config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config_schema import validate_config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict[str, Any]:
    """Read config.json (pillars + persona + cadence + model routing)."""
    return validate_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
