"""Select durable state explicitly; hosted runs must never silently use local state."""

from __future__ import annotations

import os
from pathlib import Path

from src.settings import settings
from src.state.github import GitHubStore
from src.state.ledger import Ledger
from src.state.local import LocalStore


def create_ledger() -> Ledger:
    if settings.state_backend == "github":
        return Ledger(
            GitHubStore(
                settings.state_repository, settings.state_github_token, branch=settings.state_branch
            )
        )
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise ValueError("GitHub Actions requires STATE_BACKEND=github for durable publication")
    return Ledger(LocalStore(Path(settings.state_path)))
