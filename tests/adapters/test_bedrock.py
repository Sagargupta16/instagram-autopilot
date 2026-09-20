"""Tests for Bedrock adapter -- JSON extraction + HTTP wrappers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.adapters.bedrock import (
    extract_json,
    get_async_invocation_status,
    invoke_claude,
    invoke_model,
    start_async_invocation,
    verify_auth,
)


@patch("src.adapters.bedrock.requests.post")
def test_async_start_uses_documented_route_and_body(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(ok=True, json=lambda: {"invocationArn": "arn:job"})
    body = {
        "modelInput": {"prompt": "waves"},
        "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": "s3://bucket/"}},
    }
    assert start_async_invocation("luma.ray-v2:0", body) == "arn:job"
    assert mock_post.call_args.args[0].endswith(".amazonaws.com/async-invoke")
    assert mock_post.call_args.kwargs["json"]["modelId"] == "luma.ray-v2:0"
    assert "modelId" not in body
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


@patch("src.adapters.bedrock.requests.get")
def test_async_status_encodes_arn(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"status": "Completed"}
    assert (
        get_async_invocation_status("arn:aws:bedrock:us-east-1:123:async-invoke/job")["status"]
        == "Completed"
    )
    assert (
        "/async-invoke/arn%3Aaws%3Abedrock%3Aus-east-1%3A123%3Aasync-invoke%2Fjob"
        in mock_get.call_args.args[0]
    )


class TestExtractJson:
    def test_plain_json(self) -> None:
        assert extract_json('{"k": "v"}') == {"k": "v"}

    def test_json_with_code_fence(self) -> None:
        assert extract_json('```json\n{"k": "v"}\n```') == {"k": "v"}

    def test_json_with_plain_code_fence(self) -> None:
        assert extract_json('```\n{"k": "v"}\n```') == {"k": "v"}

    def test_json_with_surrounding_whitespace(self) -> None:
        assert extract_json('   \n  {"k": "v"}  \n  ') == {"k": "v"}

    def test_json_array(self) -> None:
        assert extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            extract_json("not json at all")


class TestInvokeClaude:
    @patch("src.adapters.bedrock.requests.post")
    def test_returns_text_content(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"content": [{"type": "text", "text": "hello world"}]}),
        )
        result = invoke_claude("model-x", "say hi")
        assert result == "hello world"

    @patch("src.adapters.bedrock.requests.post")
    def test_concatenates_text_blocks_skipping_thinking(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(
                return_value={
                    "content": [
                        {"type": "thinking", "thinking": "let me think..."},
                        {"type": "text", "text": "part one "},
                        {"type": "text", "text": "part two"},
                    ]
                }
            ),
        )
        result = invoke_claude("model-x", "hi")
        assert result == "part one part two"

    @patch("src.adapters.bedrock.requests.post")
    def test_raises_when_no_text_blocks(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"content": [{"type": "thinking", "thinking": "..."}]}),
        )
        with pytest.raises(ValueError, match="No text blocks"):
            invoke_claude("model-x", "hi")

    @patch("src.adapters.bedrock.requests.post")
    def test_sends_messages_format(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"content": [{"type": "text", "text": "ok"}]}),
        )
        invoke_claude("model-x", "prompt text", max_tokens=500)
        body = mock_post.call_args.kwargs["json"]
        assert body["max_tokens"] == 500
        assert body["messages"][0]["content"] == "prompt text"


class TestInvokeModel:
    @patch("src.adapters.bedrock.requests.post")
    def test_returns_raw_json(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"images": ["base64data"]}),
        )
        result = invoke_model("nova", {"taskType": "TEXT_IMAGE"})
        assert result == {"images": ["base64data"]}


class TestVerifyAuth:
    @patch("src.adapters.bedrock.requests.post")
    def test_passes_on_2xx(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"content": [{"type": "text", "text": "ok"}]}),
        )
        verify_auth("model-x")
        body = mock_post.call_args.kwargs["json"]
        assert body["max_tokens"] == 1

    @patch("src.adapters.bedrock.requests.post")
    def test_raises_on_403(self, mock_post: MagicMock) -> None:
        resp = MagicMock(ok=False, status_code=403, text="auth failed")
        resp.raise_for_status.side_effect = requests.HTTPError("403")
        mock_post.return_value = resp
        with pytest.raises(requests.HTTPError):
            verify_auth("model-x")
