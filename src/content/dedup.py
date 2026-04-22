"""Posted-topic dedup -- keeps last 500 topics so Claude avoids repeats."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
POSTED_TOPICS_FILE = DATA_DIR / "posted_topics.json"
MAX_HISTORY = 500


def load_posted_topics() -> list[str]:
    if POSTED_TOPICS_FILE.exists():
        return json.loads(POSTED_TOPICS_FILE.read_text())
    return []


def save_posted_topic(topic: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    topics = load_posted_topics()
    topics.append(topic)
    topics = topics[-MAX_HISTORY:]
    POSTED_TOPICS_FILE.write_text(json.dumps(topics, indent=2))
