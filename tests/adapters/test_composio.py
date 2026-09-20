"""Tests for Composio v3 adapter -- execute_action + retry/error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.composio import ComposioActionError, execute_action, verify_auth


class TestExecuteAction:
    @patch("src.adapters.composio.time.sleep", return_value=None)
    @patch("src.adapters.composio.requests.post")
    def test_returns_result_on_success(self, mock_post: MagicMock, _sleep: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={"data": {"id": "abc"}, "successful": True}),
        )
        result = execute_action("SOME_ACTION", {"x": 1})
        assert result["data"]["id"] == "abc"
        assert mock_post.call_count == 1

    @patch("src.adapters.composio.time.sleep", return_value=None)
    @patch("src.adapters.composio.requests.post")
    def test_raises_on_unsuccessful(self, mock_post: MagicMock, _sleep: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(
                return_value={
                    "data": {"message": "bad url", "status_code": 400},
                    "successful": False,
                    "error": "Only photo or video accepted",
                }
            ),
        )
        with pytest.raises(ComposioActionError, match="Only photo or video"):
            execute_action("SOME_ACTION", {"x": 1})
        # Semantic errors are NOT retried -- would hit the same error anyway.
        assert mock_post.call_count == 1

    @patch("src.adapters.composio.time.sleep", return_value=None)
    @patch("src.adapters.composio.requests.post")
    def test_sends_v3_body_format(self, mock_post: MagicMock, _sleep: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={"data": {"id": "x"}, "successful": True}),
        )
        execute_action("TEST_ACTION", {"foo": "bar"})
        body = mock_post.call_args.kwargs["json"]
        assert body["arguments"] == {"foo": "bar"}
        assert "connected_account_id" in body
        assert "user_id" in body

    @patch("src.adapters.composio.time.sleep", return_value=None)
    @patch("src.adapters.composio.requests.post")
    def test_retries_on_5xx_then_succeeds(self, mock_post: MagicMock, _sleep: MagicMock) -> None:
        failing = MagicMock(ok=False, status_code=503, text="upstream down")
        succeeding = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={"data": {"id": "ok"}, "successful": True}),
        )
        mock_post.side_effect = [failing, succeeding]
        result = execute_action("INSTAGRAM_GET_POST_STATUS", {})
        assert result["data"]["id"] == "ok"
        assert mock_post.call_count == 2

    @patch("src.adapters.composio.time.sleep", return_value=None)
    @patch("src.adapters.composio.requests.post")
    def test_retries_on_network_error_then_succeeds(
        self, mock_post: MagicMock, _sleep: MagicMock
    ) -> None:
        succeeding = MagicMock(
            ok=True,
            status_code=200,
            json=MagicMock(return_value={"data": {"id": "ok"}, "successful": True}),
        )
        mock_post.side_effect = [requests.ConnectionError("boom"), succeeding]
        result = execute_action("INSTAGRAM_CREATE_MEDIA_CONTAINER", {})
        assert result["data"]["id"] == "ok"
        assert mock_post.call_count == 2


class TestVerifyAuth:
    @patch("src.adapters.composio.requests.get")
    def test_ok_does_not_raise(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(ok=True, status_code=200)
        verify_auth()  # should not raise
        assert mock_get.call_count == 1

    @patch("src.adapters.composio.requests.get")
    def test_raises_on_bad_creds(self, mock_get: MagicMock) -> None:
        bad = MagicMock(ok=False, status_code=401, text="Invalid API key")
        bad.raise_for_status.side_effect = requests.HTTPError("401")
        mock_get.return_value = bad
        with pytest.raises(requests.HTTPError):
            verify_auth()


@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("unknown outcome"),
        requests.ConnectionError("connection lost"),
        500,
        503,
    ],
)
def test_final_publication_is_never_blindly_retried(monkeypatch, failure):
    if isinstance(failure, int):
        response = requests.Response()
        response.status_code = failure
        post = MagicMock(return_value=response)
    else:
        post = MagicMock(side_effect=failure)
    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    monkeypatch.setattr("src.adapters.composio.time.sleep", lambda _: None)
    with pytest.raises(Exception) as caught:
        execute_action("INSTAGRAM_CREATE_POST", {"creation_id": "parent"})
    assert type(caught.value).__name__ == "ComposioRequestError"
    assert not isinstance(caught.value, ComposioActionError)
    assert post.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"successful": 1},
        {"successful": "false"},
        {"successful": True, "data": None},
        {"successful": True, "data": {"id": "x"}, "error": "contradictory error"},
    ],
)
def test_malformed_response_is_not_a_definite_action_failure(monkeypatch, payload):
    post = MagicMock(return_value=MagicMock(ok=True, status_code=200, json=lambda: payload))
    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    with pytest.raises(Exception) as caught:
        execute_action("INSTAGRAM_CREATE_POST", {})
    assert type(caught.value).__name__ == "ComposioResponseError"
    assert not isinstance(caught.value, ComposioActionError)
    assert post.call_count == 1


def test_invalid_json_is_an_ambiguous_response(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, status_code=200, json=MagicMock(side_effect=ValueError("invalid JSON"))
        )
    )
    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    with pytest.raises(Exception) as caught:
        execute_action("INSTAGRAM_CREATE_POST", {})
    assert type(caught.value).__name__ == "ComposioResponseError"
    assert post.call_count == 1


@pytest.mark.parametrize("wait", [60, 120, 300])
def test_http_timeout_has_processing_margin(monkeypatch, wait):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, status_code=200, json=lambda: {"successful": True, "data": {"id": "ok"}}
        )
    )
    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    execute_action("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"max_wait_seconds": wait})
    assert post.call_args.kwargs["timeout"] >= wait + 30


def test_structured_action_error_preserves_provider_details(monkeypatch):
    payload = {
        "successful": False,
        "error": {"code": 9004, "error_subcode": 2207052, "message": "Media download failed"},
        "data": None,
    }
    monkeypatch.setattr(
        "src.adapters.composio.requests.post",
        MagicMock(return_value=MagicMock(ok=True, status_code=200, json=lambda: payload)),
    )
    with pytest.raises(ComposioActionError) as caught:
        execute_action("INSTAGRAM_CREATE_MEDIA_CONTAINER", {})
    assert caught.value.result == payload
    assert caught.value.action_slug == "INSTAGRAM_CREATE_MEDIA_CONTAINER"


def test_container_network_retries_are_bounded(monkeypatch):
    post = MagicMock(side_effect=requests.Timeout("unavailable"))
    monkeypatch.setattr("src.adapters.composio.requests.post", post)
    monkeypatch.setattr("src.adapters.composio.time.sleep", lambda _: None)
    with pytest.raises(Exception) as caught:
        execute_action("INSTAGRAM_CREATE_MEDIA_CONTAINER", {})
    assert type(caught.value).__name__ == "ComposioRequestError"
    assert post.call_count == 3
