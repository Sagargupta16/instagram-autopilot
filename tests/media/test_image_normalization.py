from __future__ import annotations

import io

import pytest
from PIL import Image

from src.media import image


def picture(size: tuple[int, int] = (1024, 1280), mode: str = "RGB") -> bytes:
    output = io.BytesIO()
    Image.new(mode, size, "red").save(output, "PNG")
    return output.getvalue()


def test_normalization_produces_portrait_rgb_jpeg() -> None:
    result = image.normalize_image(picture(mode="RGBA"))
    with Image.open(io.BytesIO(result)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.mode == "RGB"
        assert decoded.size == (1080, 1350)
    assert len(result) < 8_000_000


@pytest.mark.parametrize("body", [b"", b"<html>error</html>", b"GIF89a"])
def test_rejects_invalid_image_bytes(body: bytes) -> None:
    with pytest.raises(ValueError):
        image.normalize_image(body)


def test_rejects_oversized_input_before_decoding() -> None:
    with pytest.raises(ValueError, match="size"):
        image.normalize_image(b"x" * (20_000_000 + 1))


def test_landscape_preserves_subject_edges_in_fit() -> None:
    source = Image.new("RGB", (1600, 800), "white")
    source.paste("red", (0, 0, 200, 800))
    source.paste("blue", (1400, 0, 1600, 800))
    output = io.BytesIO()
    source.save(output, "PNG")
    with Image.open(io.BytesIO(image.normalize_image(output.getvalue()))) as result:
        assert result.getpixel((5, 675))[0] > 200
        assert result.getpixel((1075, 675))[2] > 200
