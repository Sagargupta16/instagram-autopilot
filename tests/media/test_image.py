"""Tests for Nova Canvas image generation."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.media.image import generate_image


class TestGenerateImage:
    @patch("src.media.image.invoke_model")
    def test_returns_image_bytes(self, mock_invoke: MagicMock) -> None:
        fake_image = b"\x89PNG fake image"
        mock_invoke.return_value = {"images": [base64.b64encode(fake_image).decode()]}
        result = generate_image(prompt="test", model_id="amazon.nova-canvas-v1:0")
        assert result == fake_image

    @patch("src.media.image.invoke_model")
    def test_sends_correct_body(self, mock_invoke: MagicMock) -> None:
        mock_invoke.return_value = {"images": [base64.b64encode(b"x").decode()]}
        generate_image(prompt="a cool image", model_id="amazon.nova-canvas-v1:0")
        body = mock_invoke.call_args[0][1]
        assert body["taskType"] == "TEXT_IMAGE"
        assert body["textToImageParams"]["text"] == "a cool image"
        assert body["imageGenerationConfig"]["width"] == 1024
        assert body["imageGenerationConfig"]["height"] == 1024
        assert body["imageGenerationConfig"]["cfgScale"] == pytest.approx(6.5)
