"""Bounded, decoded image validation and Instagram JPEG preparation."""

from __future__ import annotations

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

PORTRAIT_SIZE = (1080, 1350)
MAX_INPUT_BYTES = 20_000_000
MAX_IMAGE_BYTES = 8_000_000
MAX_PIXELS = 25_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def decode_image(data: bytes) -> Image.Image:
    """Decode one bounded still image; reject malformed or animated payloads."""
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ValueError("Image input size must be between 1 and 20,000,000 bytes")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ALLOWED_FORMATS or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Image must be a single JPEG, PNG, or WebP frame")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image pixel count exceeds limit")
                source.load()
                return ImageOps.exif_transpose(source).copy()
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise ValueError("Invalid image payload") from error


def validate_instagram_image(data: bytes) -> None:
    """Check the actual delivered bytes, including JPEG format and dimensions."""
    if len(data) > MAX_IMAGE_BYTES or not data.startswith(b"\xff\xd8"):
        raise ValueError("Instagram image must be a JPEG below 8 MB")
    decoded = decode_image(data)
    if decoded.mode != "RGB" or decoded.size != PORTRAIT_SIZE:
        raise ValueError("Instagram image must be RGB, 1080x1350")


def normalize_image(data: bytes) -> bytes:
    """Use a small centered crop for near-4:5 frames; fit wider mismatches."""
    source = decode_image(data)
    if source.mode in {"RGBA", "LA", "P"}:
        rgba = source.convert("RGBA")
        background = Image.new("RGBA", source.size, "white")
        source = Image.alpha_composite(background, rgba).convert("RGB")
    else:
        source = source.convert("RGB")
    # Cropping at most 10% avoids clipping subjects when providers ignore aspect_ratio.
    retained = min(source.width / source.height / 0.8, 0.8 / (source.width / source.height))
    if retained >= 0.9:
        portrait = ImageOps.fit(source, PORTRAIT_SIZE, method=Image.Resampling.LANCZOS)
    else:
        portrait = ImageOps.pad(
            source, PORTRAIT_SIZE, method=Image.Resampling.LANCZOS, color=(245, 243, 239)
        )
    for quality in (92, 85, 75):
        output = io.BytesIO()
        portrait.save(output, "JPEG", quality=quality, optimize=True, progressive=False)
        result = output.getvalue()
        if len(result) <= MAX_IMAGE_BYTES:
            validate_instagram_image(result)
            return result
    raise ValueError("Normalized image exceeds Instagram byte size limit")
