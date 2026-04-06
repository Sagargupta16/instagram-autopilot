"""Generate 1080x1080 template images with text overlay using Pillow."""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
SIZE = (1080, 1080)

# Fonts available on Ubuntu (GitHub Actions) and Windows
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",  # Windows
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _draw_gradient(draw: ImageDraw.ImageDraw, colors: list[str]) -> None:
    """Draw a vertical linear gradient."""
    c1 = _hex_to_rgb(colors[0])
    c2 = _hex_to_rgb(colors[1])
    for y in range(SIZE[1]):
        ratio = y / SIZE[1]
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (SIZE[0], y)], fill=(r, g, b))


def generate_template_image(
    image_text: str,
    pillar_id: str,
    image_styles: dict[str, Any],
    account_name: str = "@sagar_sethh",
) -> Path:
    """Create a 1080x1080 branded image with text overlay.

    Returns the path to the saved image file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    style = image_styles.get(pillar_id, {
        "bg_gradient": ["#1a1a2e", "#16213e"],
        "accent": "#e94560",
        "text_color": "#ffffff",
    })

    img = Image.new("RGB", SIZE)
    draw = ImageDraw.Draw(img)

    # Background gradient
    _draw_gradient(draw, style["bg_gradient"])

    # Accent bar at top
    accent_color = _hex_to_rgb(style["accent"])
    draw.rectangle([(0, 0), (SIZE[0], 6)], fill=accent_color)

    # Main text (centered)
    text_color = _hex_to_rgb(style["text_color"])
    font_main = _load_font(56)
    wrapped = textwrap.fill(image_text, width=22)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font_main)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (SIZE[0] - text_w) // 2
    y = (SIZE[1] - text_h) // 2 - 40

    # Text shadow for readability
    shadow_offset = 3
    draw.multiline_text(
        (x + shadow_offset, y + shadow_offset),
        wrapped,
        font=font_main,
        fill=(0, 0, 0, 128),
        align="center",
    )
    draw.multiline_text(
        (x, y),
        wrapped,
        font=font_main,
        fill=text_color,
        align="center",
    )

    # Account watermark at bottom
    font_small = _load_font(28)
    wm_bbox = draw.textbbox((0, 0), account_name, font=font_small)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        ((SIZE[0] - wm_w) // 2, SIZE[1] - 80),
        account_name,
        font=font_small,
        fill=(*accent_color, 200),
    )

    # Accent bar at bottom
    draw.rectangle([(0, SIZE[1] - 6), (SIZE[0], SIZE[1])], fill=accent_color)

    output_path = OUTPUT_DIR / "post.png"
    img.save(output_path, "PNG", quality=95)
    log.info("Template image saved: %s", output_path)
    return output_path
