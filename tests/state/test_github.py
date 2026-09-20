"""GitHub state must use conditional writes, not last-writer-wins updates."""

from __future__ import annotations

import base64
import importlib
import json
from unittest.mock import Mock, patch

import pytest


def _store():
    try:
        module = importlib.import_module("src.state.github")
    except ModuleNotFoundError:
        pytest.fail("GitHub CAS state must survive runner termination")
    return module.GitHubStore("owner/repo", "dummy-token")


def _response(status, payload):
    response = Mock(status_code=status, ok=status < 400)
    response.json.return_value = payload
    response.raise_for_status.side_effect = RuntimeError("HTTP rejected") if status >= 400 else None
    return response


def test_read_decodes_remote_state_and_retains_revision():
    store = _store()
    data = {"version": 1, "slots": {}, "history": []}
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    with patch(
        "src.state.github.requests.get",
        return_value=_response(200, {"sha": "rev1", "content": encoded}),
    ) as get:
        assert store.read() == (data, "rev1")
    assert get.call_args.kwargs["params"] == {"ref": "autopilot-state"}


def test_save_requires_the_read_revision():
    store = _store()
    data = {"version": 1, "slots": {}, "history": []}
    with patch("src.state.github.requests.put", return_value=_response(200, {})) as put:
        store.save(data, "rev1")
    assert put.call_args.kwargs["json"]["sha"] == "rev1"
    assert put.call_args.kwargs["json"]["branch"] == "autopilot-state"
    assert "[skip ci]" in put.call_args.kwargs["json"]["message"]


def test_write_conflict_is_distinguished_from_network_failure():
    store = _store()
    from src.state.store import ConflictError

    with (
        patch("src.state.github.requests.put", return_value=_response(409, {})),
        pytest.raises(ConflictError),
    ):
        store.save({"version": 1, "slots": {}, "history": []}, "stale")


def test_missing_state_creates_a_dedicated_branch():
    store = _store()
    with (
        patch(
            "src.state.github.requests.get",
            side_effect=[
                _response(404, {}),
                _response(404, {}),
                _response(200, {"object": {"sha": "base-sha"}}),
            ],
        ),
        patch("src.state.github.requests.post", return_value=_response(201, {})) as post,
    ):
        data, revision = store.read()
    assert revision is None
    assert data["slots"] == {}
    assert post.call_args.kwargs["json"] == {"ref": "refs/heads/autopilot-state", "sha": "base-sha"}


def test_unsafe_repository_or_branch_rejected():
    for repo, branch in [("../other", "state"), ("owner/repo", "main"), ("owner/repo", "../bad")]:
        with pytest.raises(ValueError):
            module = importlib.import_module("src.state.github")
            module.GitHubStore(repo, "dummy", branch=branch)
