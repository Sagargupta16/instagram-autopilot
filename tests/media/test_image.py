"""Tests for Nova Canvas image generation."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.media.image import MAX_PROMPT_CHARS, SEED_MAX, SEED_MIN, generate_image


def _fake_response(body: bytes = b"x") -> dict:
    return {"images": [base64.b64encode(body).decode()]}


class TestGenerateImage:
    @patch("src.media.image.invoke_model")
    def test_returns_image_bytes(self, mock_invoke: MagicMock) -> None:
        fake_image = b"\x89PNG fake image"
        mock_invoke.return_value = _fake_response(fake_image)
        result = generate_image(prompt="test", model_id="amazon.nova-canvas-v1:0")
        assert result == fake_image

    @patch("src.media.image.invoke_model")
    def test_sends_photorealism_style(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="a cool image", model_id="amazon.nova-canvas-v1:0")
        body = mock_invoke.call_args[0][1]
        assert body["taskType"] == "TEXT_IMAGE"
        assert body["textToImageParams"]["style"] == "PHOTOREALISM"
        assert body["textToImageParams"]["text"] == "a cool image"

    @patch("src.media.image.invoke_model")
    def test_default_cfg_scale_is_strict_edge(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0")
        body = mock_invoke.call_args[0][1]
        # 7.5 sits at the stricter end of "balanced" per Nova docs,
        # which helps enforce per-slide prompt differences.
        assert body["imageGenerationConfig"]["cfgScale"] == pytest.approx(7.5)
        assert body["imageGenerationConfig"]["width"] == 1024
        assert body["imageGenerationConfig"]["height"] == 1024
        assert body["imageGenerationConfig"]["quality"] == "premium"

    @patch("src.media.image.invoke_model")
    def test_randomizes_seed_by_default(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0")
        body = mock_invoke.call_args[0][1]
        seed = body["imageGenerationConfig"]["seed"]
        # Must be an int in Nova's valid range, and NOT the default 12 always
        # (that's the bug we are fixing by randomizing).
        assert isinstance(seed, int)
        assert SEED_MIN <= seed <= SEED_MAX

    @patch("src.media.image.invoke_model")
    def test_different_calls_use_different_seeds(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        seeds: set[int] = set()
        # With range 0..2**31-2, 20 draws colliding is astronomically unlikely.
        for _ in range(20):
            generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0")
            seeds.add(mock_invoke.call_args[0][1]["imageGenerationConfig"]["seed"])
        assert len(seeds) > 1, "seeds should vary across calls"

    @patch("src.media.image.invoke_model")
    def test_explicit_seed_is_respected(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0", seed=42)
        body = mock_invoke.call_args[0][1]
        assert body["imageGenerationConfig"]["seed"] == 42

    @patch("src.media.image.invoke_model")
    def test_truncates_prompt_over_limit(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        oversized = "A" * (MAX_PROMPT_CHARS + 500)
        generate_image(prompt=oversized, model_id="amazon.nova-canvas-v1:0")
        sent = mock_invoke.call_args[0][1]["textToImageParams"]["text"]
        assert len(sent) == MAX_PROMPT_CHARS

    @patch("src.media.image.invoke_model")
    def test_does_not_truncate_short_prompt(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = _fake_response()
        short = "short prompt"
        generate_image(prompt=short, model_id="amazon.nova-canvas-v1:0")
        sent = mock_invoke.call_args[0][1]["textToImageParams"]["text"]
        assert sent == short

    @patch("src.media.image.invoke_model")
    def test_raises_when_rai_strips_all_images(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = {"images": [], "error": "Content blocked"}
        with pytest.raises(RuntimeError, match="Content blocked"):
            generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0")

    @patch("src.media.image.invoke_model")
    def test_raises_when_images_key_missing(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = {}
        with pytest.raises(RuntimeError, match="no images"):
            generate_image(prompt="x", model_id="amazon.nova-canvas-v1:0")
