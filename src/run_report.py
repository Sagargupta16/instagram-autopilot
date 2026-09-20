"""Machine-readable run outcome and a concise GitHub Actions summary."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_summary(outcome: dict[str, Any]) -> None:
    output = Path("output/run-summary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [f"Instagram Autopilot: **{outcome['status']}**", ""]
        lines.extend(f"- {key}: {value}" for key, value in outcome.items() if key != "status")
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
