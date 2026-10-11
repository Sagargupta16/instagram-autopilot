"""Visual variants for SVG Reels: a checked palette, kicker wording and icon tile shape.

Palettes follow the owner's svg-forge themes (midnight is the github-dark accent, violet the
Catppuccin Mocha base and mauve, amber the Gruvbox dark orange). Every text color is at least
4.5:1 and every mark at least 3:1 on what it sits on, also at DIM opacity, and the tests check
each pair. Posts rotate through LOOKS so consecutive posts never share a look.
"""

from __future__ import annotations

from dataclasses import dataclass

DIM = 0.7  # opacity of finished steps and milestones while a later one is active


@dataclass(frozen=True)
class Look:
    name: str
    bg: str
    card: str
    take: str
    text: str
    muted: str
    accent: str
    accent_text: str
    packet: str
    track: str  # decoration, always drawn below 50% opacity
    tile: str  # "circle" or "square" behind step and milestone icons
    kickers: tuple[str, str, str]  # steps, stat, timeline

    @property
    def ink(self) -> str:
        """Text on accent fills."""
        return self.bg

    def text_on(self) -> dict[str, tuple[str, ...]]:
        surfaces = (self.bg, self.card, self.take)
        return {self.text: surfaces, self.muted: surfaces, self.accent_text: surfaces}

    def mark_on(self) -> dict[str, tuple[str, ...]]:
        return {
            self.accent: (self.bg, self.card, self.take),
            self.muted: (self.bg,),
            self.packet: (self.bg, self.card),
        }

    def kicker(self, kind: str) -> str:
        return self.kickers[("steps", "stat", "timeline").index(kind)]


LOOKS = (
    Look(
        name="midnight",
        bg="#0b1020",
        card="#151d33",
        take="#1b2f5c",
        text="#f8fafc",
        muted="#c3cfe2",
        accent="#60a5fa",
        accent_text="#93c5fd",
        packet="#e0f2fe",
        track="#334155",
        tile="circle",
        kickers=("HOW IT WORKS", "BY THE NUMBERS", "TIMELINE"),
    ),
    Look(
        name="violet",
        bg="#1e1e2e",
        card="#313244",
        take="#45385f",
        text="#f5f3ff",
        muted="#cdd6f4",
        accent="#cba6f7",
        accent_text="#ddc7fb",
        packet="#f5e0dc",
        track="#585b70",
        tile="square",
        kickers=("STEP BY STEP", "WHAT THE DATA SAYS", "HOW IT HAPPENED"),
    ),
    Look(
        name="amber",
        bg="#1c1917",
        card="#2c2622",
        take="#4a3420",
        text="#fbf1c7",
        muted="#e5d5b0",
        accent="#fe8019",
        accent_text="#fabd2f",
        packet="#fde68a",
        track="#57534e",
        tile="circle",
        kickers=("UNDER THE HOOD", "THE BIG PICTURE", "MILESTONES"),
    ),
)


def look(index: int) -> Look:
    return LOOKS[index % len(LOOKS)]
