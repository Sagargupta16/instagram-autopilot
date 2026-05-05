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
        result = execute_action("TEST", {})
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
        result = execute_action("TEST", {})
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
