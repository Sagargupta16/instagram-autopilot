"""Tests for Composio v3 adapter -- execute_action + error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.adapters.composio import ComposioActionError, execute_action


class TestExecuteAction:
    @patch("src.adapters.composio.requests.post")
    def test_returns_result_on_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"data": {"id": "abc"}, "successful": True}),
        )
        result = execute_action("SOME_ACTION", {"x": 1})
        assert result["data"]["id"] == "abc"

    @patch("src.adapters.composio.requests.post")
    def test_raises_on_unsuccessful(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
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

    @patch("src.adapters.composio.requests.post")
    def test_sends_v3_body_format(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"data": {"id": "x"}, "successful": True}),
        )
        execute_action("TEST_ACTION", {"foo": "bar"})
        body = mock_post.call_args.kwargs["json"]
        assert body["arguments"] == {"foo": "bar"}
        assert "connected_account_id" in body
        assert "user_id" in body
