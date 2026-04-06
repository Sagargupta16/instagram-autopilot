"""Tests for utility functions (template images, image hosting)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from src.utils.template_image import _hex_to_rgb, generate_template_image


class TestHexToRgb:
    def test_basic_colors(self) -> None:
        assert _hex_to_rgb("#ff0000") == (255, 0, 0)
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_without_hash(self) -> None:
        assert _hex_to_rgb("ffffff") == (255, 255, 255)
        assert _hex_to_rgb("000000") == (0, 0, 0)

    def test_mixed_case(self) -> None:
        assert _hex_to_rgb("#FF0000") == (255, 0, 0)
        assert _hex_to_rgb("#aaBBcc") == (170, 187, 204)


class TestGenerateTemplateImage:
    def test_creates_image_file(
        self, sample_image_styles: dict[str, Any], tmp_path: Path
    ) -> None:
        with patch("src.utils.template_image.OUTPUT_DIR", tmp_path):
            path = generate_template_image(
                image_text="Test Image Text",
                pillar_id="cognitive_biases",
                image_styles=sample_image_styles,
            )
            assert path.exists()
            assert path.suffix == ".png"

    def test_image_dimensions(
        self, sample_image_styles: dict[str, Any], tmp_path: Path
    ) -> None:
        from PIL import Image

        with patch("src.utils.template_image.OUTPUT_DIR", tmp_path):
            path = generate_template_image(
                image_text="Test",
                pillar_id="cognitive_biases",
                image_styles=sample_image_styles,
            )
            img = Image.open(path)
            assert img.size == (1080, 1080)

    def test_uses_fallback_style_for_unknown_pillar(self, tmp_path: Path) -> None:
        with patch("src.utils.template_image.OUTPUT_DIR", tmp_path):
            path = generate_template_image(
                image_text="Fallback test",
                pillar_id="nonexistent_pillar",
                image_styles={},
            )
            assert path.exists()


class TestImageHost:
    @patch("src.utils.image_host.requests.post")
    def test_upload_returns_url(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"url": "https://i.ibb.co/abc123/image.png"}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        from src.utils.image_host import upload_to_imgbb

        url = upload_to_imgbb(img_path, api_key="test-key")
        assert url == "https://i.ibb.co/abc123/image.png"

    @patch("src.utils.image_host.requests.post")
    def test_sends_base64_image_data(self, mock_post: MagicMock, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"url": "https://example.com/img.png"}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake image data")

        from src.utils.image_host import upload_to_imgbb

        upload_to_imgbb(img_path, api_key="my-key")

        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["key"] == "my-key"
        assert call_data["expiration"] == 86400
        assert len(call_data["image"]) > 0  # base64 encoded
