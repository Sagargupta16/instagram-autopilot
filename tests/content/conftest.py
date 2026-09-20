"""Content response fixtures independent of publishing test fixtures."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture()
def sample_caption_data(sample_caption_data: dict[str, Any]) -> dict[str, Any]:
    return {
        **sample_caption_data,
        "audio_theme": "cinematic",
        "location_query": None,
        "alt_texts": [
            "A fragmented mirror in warm light.",
            "A conceptual view of illuminated neural connections.",
            "Hands holding a fading photograph.",
            "A glass brain sculpture with cracks.",
            "An empty chair in a pool of light.",
        ],
        "slide_notes": [
            "Introduce the difference between a memory and a recording.",
            "Explain that recall involves reconstruction.",
            "Illustrate how a photograph can prompt recollection.",
            "Show why certainty alone is a poor check.",
            "Suggest comparing a recollection with contemporaneous notes.",
        ],
    }
