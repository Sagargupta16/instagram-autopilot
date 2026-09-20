"""Validate strategy before any provider request or paid generation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Weight = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ClockTime = Annotated[str, Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")]


class Window(BaseModel):
    start: ClockTime = "04:00"
    end: ClockTime = "20:00"

    @model_validator(mode="after")
    def ordered(self) -> Window:
        if self.start >= self.end:
            raise ValueError("Posting window must start before it ends on the same UTC date")
        return self


class Cadence(BaseModel):
    max_posts_per_day: int = Field(default=2, ge=0, le=24)
    post_probability: list[Weight] = Field(default=[0.20, 0.55, 0.25], min_length=1, max_length=25)
    window_utc: Window = Field(default_factory=Window)
    min_gap_minutes: int = Field(default=180, ge=1, le=1440)
    schedule_buffer_minutes: int = Field(default=40, ge=1, le=180)
    skip_probability: float = Field(default=0.05, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def positive_total(self) -> Cadence:
        if sum(self.post_probability) <= 0:
            raise ValueError("At least one posting probability must be positive")
        start = sum(
            int(part) * factor
            for part, factor in zip(self.window_utc.start.split(":"), (60, 1), strict=True)
        )
        end = sum(
            int(part) * factor
            for part, factor in zip(self.window_utc.end.split(":"), (60, 1), strict=True)
        )
        if self.schedule_buffer_minutes >= end - start:
            raise ValueError("Posting window must exceed the scheduler/generation buffer")
        return self


class Pillar(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(min_length=1)
    content_format: Literal["carousel", "image", "reel"] = "carousel"
    hashtags: list[str]
    image_style: str = Field(min_length=1)
    weight: Weight = 1


class Persona(BaseModel):
    model_config = ConfigDict(extra="allow")
    tone: str = Field(min_length=1)
    name: str = ""


class Models(BaseModel):
    text: str = Field(min_length=1)
    image: str = Field(min_length=1)
    video: str = Field(min_length=1)


class Strategy(BaseModel):
    model_config = ConfigDict(extra="allow")
    cadence: Cadence = Field(default_factory=Cadence)
    pillars: list[Pillar] = Field(min_length=1)
    persona: Persona
    models: Models

    @model_validator(mode="after")
    def unique_pillars(self) -> Strategy:
        ids = [pillar.id for pillar in self.pillars]
        if len(ids) != len(set(ids)) or not any(pillar.weight for pillar in self.pillars):
            raise ValueError("Pillars need unique IDs and at least one positive weight")
        return self


def validate_config(data: Any) -> dict[str, Any]:
    return Strategy.model_validate(data).model_dump()
