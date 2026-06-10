"""Tests for Stable Image Ultra image generation."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.media.image import MAX_PROMPT_CHARS, SEED_MAX, SEED_MIN, generate_image

MODEL = "stability.stable-image-ultra-v1:1"


def _fake_response(body: bytes = b"x") -> dict:
    return {"images": [base64.b64encode(body).decode()], "finish_reasons": [None]}


class TestGenerateImage:
    @patch("src.media.image.invoke_model")
    def test_returns_image_bytes(self, mock_invoke: MagicMock) -> None:
        fake_image = b"\x89PNG fake image"
        mock_invoke.return_value = _fake_response(fake_image)
        result = generate_image(prompt="test", model_id=MODEL)
        assert result == fake_image

    @patch("src.media.image.invoke_model")
    def test_sends_stability_request_shape(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="a cool image", model_id=MODEL)
        body = mock_invoke.call_args[0][1]
        assert body["prompt"] == "a cool image"
        assert body["aspect_ratio"] == "1:1"
        assert body["output_format"] == "png"
        # No native style enum on Stability -- the anti-illustration guard
        # must live in the negative prompt instead.
        assert "illustration" in body["negative_prompt"]

    @patch("src.media.image.invoke_model")
    def test_randomizes_seed_by_default(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="x", model_id=MODEL)
        seed = mock_invoke.call_args[0][1]["seed"]
        assert isinstance(seed, int)
        assert SEED_MIN <= seed <= SEED_MAX

    @patch("src.media.image.invoke_model")
    def test_different_calls_use_different_seeds(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        seeds: set[int] = set()
        # With range 1..2**32-2, 20 draws colliding is astronomically unlikely.
        for _ in range(20):
            generate_image(prompt="x", model_id=MODEL)
            seeds.add(mock_invoke.call_args[0][1]["seed"])
        assert len(seeds) > 1, "seeds should vary across calls"

    @patch("src.media.image.invoke_model")
    def test_explicit_seed_is_respected(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="x", model_id=MODEL, seed=42)
        assert mock_invoke.call_args[0][1]["seed"] == 42

    @patch("src.media.image.invoke_model")
    def test_truncates_prompt_over_limit(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        oversized = "A" * (MAX_PROMPT_CHARS + 500)
        generate_image(prompt=oversized, model_id=MODEL)
        sent = mock_invoke.call_args[0][1]["prompt"]
        assert len(sent) == MAX_PROMPT_CHARS

    @patch("src.media.image.invoke_model")
    def test_does_not_truncate_short_prompt(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        short = "short prompt"
        generate_image(prompt=short, model_id=MODEL)
        assert mock_invoke.call_args[0][1]["prompt"] == short

    @patch("src.media.image.invoke_model")
    def test_raises_when_content_filtered(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = {
            "images": ["AAAA"],
            "finish_reasons": ["Filter reason: prompt"],
        }
        with pytest.raises(RuntimeError, match="filtered"):
            generate_image(prompt="x", model_id=MODEL)

    @patch("src.media.image.invoke_model")
    def test_raises_when_images_key_missing(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = {}
        with pytest.raises(RuntimeError, match="no images"):
            generate_image(prompt="x", model_id=MODEL)
