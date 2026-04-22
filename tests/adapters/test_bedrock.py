"""Tests for Bedrock adapter -- JSON extraction + HTTP wrappers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.bedrock import extract_json, invoke_claude, invoke_model


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
            json=MagicMock(return_value={"content": [{"text": "hello world"}]}),
        )
        result = invoke_claude("model-x", "say hi")
        assert result == "hello world"

    @patch("src.adapters.bedrock.requests.post")
    def test_sends_messages_format(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"content": [{"text": "ok"}]}),
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
