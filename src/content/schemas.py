"""Runtime contracts for model output before any media work is started."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from src.content.sources import normalize_topic


def _meaningful_text(value: str) -> str:
    if not normalize_topic(value):
        raise ValueError("text must contain words, not only punctuation")
    return value


def _positive_scene(value: str) -> str:
    if re.search(r"\b(no|not|without)\b", value, re.IGNORECASE):
        raise ValueError("describe positive scene contents; exclusions belong in negative_prompt")
    if re.search(
        r"\b(text|typography|lettering|captions?|headlines?|logos?|watermarks?|"
        r"infographics?|labeled|labelled)\b",
        value,
        re.IGNORECASE,
    ):
        raise ValueError("image/video scenes must not request rendered text or graphics")
    return value


Nonempty = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
    AfterValidator(_meaningful_text),
]
ImagePrompt = Annotated[Nonempty, Field(max_length=1500), AfterValidator(_positive_scene)]
AltText = Annotated[Nonempty, Field(max_length=1000)]
SlideNote = Annotated[Nonempty, Field(max_length=500)]


class CaptionContent(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    caption: Annotated[Nonempty, Field(max_length=1800)]
    hashtags: Annotated[Nonempty, Field(max_length=400)]
    x_post: Annotated[Nonempty, Field(max_length=280)]
    image_prompts: Annotated[list[ImagePrompt], Field(min_length=5, max_length=5)]
    video_prompt: Annotated[Nonempty, Field(max_length=400), AfterValidator(_positive_scene)]
    location_query: Annotated[Nonempty, Field(max_length=200)] | None
    audio_theme: Literal["chill", "upbeat", "cinematic", "ambient", "energetic"]
    alt_texts: Annotated[list[AltText], Field(min_length=5, max_length=5)]
    slide_notes: Annotated[list[SlideNote], Field(min_length=5, max_length=5)] | None = None

    @field_validator("hashtags")
    @classmethod
    def valid_hashtags(cls, value: str) -> str:
        tags = value.split()
        if len(tags) > 30 or any(not re.fullmatch(r"#\w+", tag) for tag in tags):
            raise ValueError("hashtags must contain at most 30 space-separated #tags")
        if len({tag.casefold() for tag in tags}) != len(tags):
            raise ValueError("hashtags must be unique")
        return " ".join(tags)

    @field_validator("location_query")
    @classmethod
    def nullable_place(cls, value: str | None) -> str | None:
        if value is not None and value.casefold() in {"null", "none", "n/a", "unknown"}:
            raise ValueError("use JSON null when no specific real place applies")
        return value

    @field_validator("image_prompts", "alt_texts", "slide_notes")
    @classmethod
    def distinct_slides(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and len({normalize_topic(value) for value in values}) != 5:
            raise ValueError("five distinct slides are required, each advancing the story")
        return values

    @model_validator(mode="after")
    def caption_fits_instagram(self) -> CaptionContent:
        if len(f"{self.caption}\n\n{self.hashtags}") > 2200:
            raise ValueError("caption and hashtags together must fit 2200 characters")
        return self


class TopicChoice(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    topic: Annotated[Nonempty, Field(max_length=200)]
    source_indices: Annotated[list[int], Field(max_length=3)] = Field(default_factory=list)
