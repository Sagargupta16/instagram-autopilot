"""Durable GitHub Contents storage on a dedicated branch with revision checks."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import requests

from src.state.store import ConflictError, empty_state, validate_state


class GitHubStore:
    def __init__(self, repository: str, token: str, *, branch: str = "autopilot-state") -> None:
        if not re.fullmatch(r"[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*", repository) or not token:
            raise ValueError("GitHub state requires an owner/repository and token")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", branch) or branch in {"main", "master"}:
            raise ValueError("Publication state requires its own simple branch name")
        self.base = f"https://api.github.com/repos/{repository}"
        self.url = f"{self.base}/contents/data/publication_state.json"
        self.branch = branch
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def read(self) -> tuple[dict[str, Any], str | None]:
        response = requests.get(
            self.url, headers=self.headers, params={"ref": self.branch}, timeout=30
        )
        if response.status_code == 404:
            self._ensure_branch()
            return empty_state(), None
        response.raise_for_status()
        payload = response.json()
        raw = base64.b64decode(payload["content"])
        return validate_state(json.loads(raw)), payload["sha"]

    def _ensure_branch(self) -> None:
        response = requests.get(
            f"{self.base}/git/ref/heads/{self.branch}", headers=self.headers, timeout=30
        )
        if response.status_code != 404:
            response.raise_for_status()
            return
        base = requests.get(f"{self.base}/git/ref/heads/main", headers=self.headers, timeout=30)
        base.raise_for_status()
        created = requests.post(
            f"{self.base}/git/refs",
            headers=self.headers,
            json={"ref": f"refs/heads/{self.branch}", "sha": base.json()["object"]["sha"]},
            timeout=30,
        )
        if created.status_code == 422:
            # Another first-run worker may have created the same branch.
            check = requests.get(
                f"{self.base}/git/ref/heads/{self.branch}", headers=self.headers, timeout=30
            )
            check.raise_for_status()
        else:
            created.raise_for_status()

    def save(self, data: dict[str, Any], revision: str | None) -> None:
        raw = json.dumps(validate_state(data), ensure_ascii=False).encode("utf-8")
        if len(raw) > 900_000:
            raise ValueError(
                "Publication state exceeds its safe size; archive old resolved records"
            )
        payload: dict[str, Any] = {
            "message": "chore: checkpoint publication state [skip ci]",
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": self.branch,
        }
        if revision:
            payload["sha"] = revision
        response = requests.put(self.url, headers=self.headers, json=payload, timeout=30)
        if response.status_code in {409, 422}:
            raise ConflictError("GitHub state changed or rejected the conditional write")
        response.raise_for_status()
