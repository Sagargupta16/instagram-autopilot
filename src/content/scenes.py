"""Validated scenes for the animated SVG Reel formats, grounded before any rendering."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from src.content.grounding import evidence_text, published_text, ungrounded
from src.content.hooks import weak_hook
from src.content.schemas import Nonempty, hashtag_list
from src.content.sources import publication_name
from src.content.voice import meta_commentary
from src.media.lucide import ICONS
from src.media.reel_svg import LayoutError, compose

CHANGE = re.compile(
    r"\b(?:declin\w*|decreas\w*|increas\w*|drop\w*|fell|fall\w*|plung\w*|rise[sn]?|rising|rose"
    r"|grew|grow\w*|surg\w*|jump\w*|climb\w*|soar\w*|shr[iu]nk\w*|down|lost|loss(?:es)?|gain\w*)\b",
    re.IGNORECASE,
)
STAT_VALUE = (
    r"^[$€£¥₹]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?i:%|\s?(?:k|m|bn|tn|thousand|million|billion|trillion))?$"
)
StatValue = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, max_length=14, pattern=STAT_VALUE)
]
Label = Annotated[Nonempty, Field(max_length=18)]
Detail = Annotated[Nonempty, Field(max_length=48)]
Hook = Annotated[Nonempty, Field(max_length=42)]
Takeaway = Annotated[Nonempty, Field(max_length=70)]
Headline = Annotated[Nonempty, Field(max_length=48)]
Context = Annotated[Nonempty, Field(max_length=80)]
Unit = Annotated[Nonempty, Field(max_length=24)]
BarLabel = Annotated[Nonempty, Field(max_length=16)]
PointLabel = Annotated[Nonempty, Field(max_length=8)]
DateLabel = Annotated[Nonempty, Field(max_length=12), StringConstraints(pattern=r"\d")]
Event = Annotated[Nonempty, Field(max_length=44)]
Cell = Annotated[Nonempty, Field(max_length=40)]
Belief = Annotated[Nonempty, Field(max_length=64)]
Truth = Annotated[Nonempty, Field(max_length=84)]
FEED_PREVIEW = 125  # caption characters the feed shows before "... more"


def _known_icon(name: str) -> str:
    if name not in ICONS:
        raise ValueError(f"unknown icon {name!r}; pick a name from the icon list or omit icon")
    return name


Icon = Annotated[str, StringConstraints(strict=True), AfterValidator(_known_icon)]


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Step(_Strict):
    label: Label
    detail: Detail
    icon: Icon | None = None


class StepsScene(_Strict):
    kind: Literal["steps"]
    hook: Hook
    steps: Annotated[list[Step], Field(min_length=3, max_length=6)]
    takeaway: Takeaway


class Bar(_Strict):
    label: BarLabel
    value: StatValue


class Point(_Strict):
    label: PointLabel
    value: StatValue


class StatScene(_Strict):
    kind: Literal["stat"]
    variant: Literal["big_number", "bars", "ring", "line"]
    headline: Headline
    icon: Icon | None = None
    value: StatValue | None = None
    context: Context | None = None
    bars: Annotated[list[Bar], Field(min_length=2, max_length=6)] | None = None
    points: Annotated[list[Point], Field(min_length=3, max_length=8)] | None = None
    unit: Unit | None = None
    takeaway: Takeaway
    source_index: Annotated[int, Field(ge=0, le=2)]

    @model_validator(mode="after")
    def one_visual(self) -> StatScene:
        needs = {
            "big_number": ("value", "context"),
            "ring": ("value", "context"),
            "bars": ("bars",),
            "line": ("points",),
        }[self.variant]
        for field in ("value", "context", "bars", "points"):
            if (getattr(self, field) is not None) != (field in needs):
                rule = "requires" if field in needs else "must omit"
                raise ValueError(f"variant {self.variant} {rule} {field}")
        if self.variant == "ring" and not (
            self.value.endswith("%") and 0 <= float(self.value[:-1].replace(",", "")) <= 100
        ):
            raise ValueError("ring value must be a percentage from 0% to 100%")
        if self.variant == "ring" and CHANGE.search(self.context):
            # a ring filled to 99% for a 99% decline reads as 99% remaining
            raise ValueError(
                "ring shows a share of a whole; a change (decline, rise, drop, growth) "
                "must use variant big_number"
            )
        labels = [item.label.casefold() for item in self.bars or self.points or []]
        if len(set(labels)) != len(labels):
            raise ValueError("bar and point labels must be distinct")
        return self


class Milestone(_Strict):
    date: DateLabel
    event: Event
    icon: Icon | None = None


class TimelineScene(_Strict):
    kind: Literal["timeline"]
    hook: Hook
    milestones: Annotated[list[Milestone], Field(min_length=4, max_length=6)]
    takeaway: Takeaway


class Side(_Strict):
    name: Label
    icon: Icon | None = None


class Row(_Strict):
    aspect: Label
    left: Cell
    right: Cell


class VersusScene(_Strict):
    kind: Literal["versus"]
    hook: Hook
    left: Side
    right: Side
    rows: Annotated[list[Row], Field(min_length=3, max_length=4)]
    takeaway: Takeaway

    @model_validator(mode="after")
    def two_things(self) -> VersusScene:
        if self.left.name.casefold() == self.right.name.casefold():
            raise ValueError("a versus scene compares two different things")
        return self


class Myth(_Strict):
    myth: Belief
    fact: Truth


class MythsScene(_Strict):
    kind: Literal["myths"]
    hook: Hook
    items: Annotated[list[Myth], Field(min_length=2, max_length=3)]
    takeaway: Takeaway


Scene = Annotated[
    StepsScene | StatScene | TimelineScene | VersusScene | MythsScene,
    Field(discriminator="kind"),
]


class SvgReelContent(_Strict):
    """Everything an SVG Reel publishes: no image prompts, since no photo is ever made."""

    caption: Annotated[Nonempty, Field(max_length=1800)]
    hashtags: Annotated[Nonempty, Field(max_length=400), AfterValidator(hashtag_list)]
    x_post: Annotated[Nonempty, Field(max_length=280)]
    scene: Scene

    @model_validator(mode="after")
    def caption_fits_instagram(self) -> SvgReelContent:
        if len(f"{self.caption}\n\n{self.hashtags}") > 2200:
            raise ValueError("caption and hashtags together must fit 2200 characters")
        first = self.caption.split("\n", 1)[0].strip()
        if len(first) > FEED_PREVIEW:
            raise ValueError(
                f"the caption's first line is {len(first)} characters, but the feed shows about "
                f"{FEED_PREVIEW} before '... more': open with one complete sentence under "
                f"{FEED_PREVIEW} characters that names the subject"
            )
        return self


def scene_texts(scene: dict[str, Any]) -> list[str]:
    """Every model-written string a viewer can see in the scene."""
    out: list[str] = []
    for key, value in scene.items():
        if key in {"kind", "variant", "source_index", "icon"}:
            continue
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend(text for item in value for text in scene_texts(item))
        elif isinstance(value, dict):
            out.extend(scene_texts(value))
    return out


def source_line(scene: dict[str, Any], sources: list[dict]) -> str | None:
    """Attribution drawn from adapter metadata, never from model text."""
    if scene["kind"] == "stat":
        return f"Source: {publication_name(sources[scene['source_index']])}"
    if scene["kind"] in {"timeline", "myths"} and sources:
        names = list(dict.fromkeys(publication_name(source) for source in sources))[:2]
        return "Source: " + " and ".join(names)
    return None


def grounding_problems(
    scene: dict[str, Any], caption: str, kind: str, sources: list[dict]
) -> list[str]:
    """Numbers on screen or in the caption that the adapters' evidence does not contain."""
    problems = []
    cited = sources
    if kind == "stat":
        index = scene.get("source_index")
        if not isinstance(index, int) or not 0 <= index < len(sources):
            return ["scene.source_index must reference a supplied source record"]
        cited = [sources[index]]
    if missing := ungrounded(scene_texts(scene), evidence_text(cited)):
        problems.append(
            "every number and date in the scene must appear in the cited source text; "
            f"not found there: {', '.join(missing)}. Use only figures quoted in the evidence"
        )
    if missing := ungrounded([published_text(caption)], evidence_text(sources)):
        problems.append(
            "the caption may only use numbers that appear in the source text; "
            f"not found there: {', '.join(missing)}. Never compute, compare or round figures"
        )
    return problems


def _early_problems(raw: object, kind: str, sources: list[dict]) -> list[str]:
    """Grounding problems readable from unvalidated output, so one repair can fix everything."""
    if not isinstance(raw, dict) or not isinstance(raw.get("scene"), dict):
        return []
    caption = raw.get("caption") if isinstance(raw.get("caption"), str) else ""
    try:
        return grounding_problems(raw["scene"], caption, kind, sources)
    except (AttributeError, TypeError):
        return []


def validate_svg_content(raw: object, *, kind: str, sources: list[dict]) -> SvgReelContent:
    """Schema, grounding of every number, and a dry layout; ValueError triggers one repair."""
    try:
        content = SvgReelContent.model_validate(raw)
    except ValidationError as error:
        if extra := _early_problems(raw, kind, sources):
            raise ValueError(f"{error}\nAlso: " + "; ".join(extra)) from error
        raise
    scene = content.scene.model_dump()
    if scene["kind"] != kind:
        raise ValueError(f'scene.kind must be "{kind}" for this pillar')
    if problems := grounding_problems(scene, content.caption, kind, sources):
        raise ValueError("; ".join(problems))
    if problems := meta_commentary(scene, content.caption):
        raise ValueError("; ".join(problems))
    if problems := weak_hook(scene):
        raise ValueError("; ".join(problems))
    try:
        compose(scene, source_line=source_line(scene, sources))
    except LayoutError as error:
        raise ValueError(f"scene does not fit the Reel layout: {error}") from error
    return content
