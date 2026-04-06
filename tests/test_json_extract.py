"""Tests for JSON extraction from Bedrock responses."""

from __future__ import annotations

import pytest

from src.generator.text import _extract_json


class TestExtractJson:
    def test_plain_json(self) -> None:
        result = _extract_json('{"topic": "test"}')
        assert result == {"topic": "test"}

    def test_json_with_code_fence(self) -> None:
        raw = '```json\n{"topic": "fenced"}\n```'
        result = _extract_json(raw)
        assert result == {"topic": "fenced"}

    def test_json_with_plain_code_fence(self) -> None:
        raw = '```\n{"topic": "plain fence"}\n```'
        result = _extract_json(raw)
        assert result == {"topic": "plain fence"}

    def test_json_with_surrounding_whitespace(self) -> None:
        raw = '\n\n  {"topic": "spaced"}  \n\n'
        result = _extract_json(raw)
        assert result == {"topic": "spaced"}

    def test_json_array(self) -> None:
        raw = '```json\n[{"title": "a"}, {"title": "b"}]\n```'
        result = _extract_json(raw)
        assert len(result) == 2

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(Exception):
            _extract_json("this is not json at all")
