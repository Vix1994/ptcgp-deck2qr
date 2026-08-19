"""Strict parser for Deck Text Format v1."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from .model import ALLOWED_ENERGIES, CardRef, Deck, DeckCard, Section

HEADER = "# PTCGP-DECK 1"
_CARD_LINE = re.compile(
    r"^(?P<count>[1-9][0-9]*) (?P<name>[^|\n]+) \| "
    r"(?P<set>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)-(?P<number>[0-9]+)$"
)


class DeckTextError(ValueError):
    """Raised when Deck Text syntax or version is invalid."""


def parse_deck_text(text: str) -> Deck:
    """Parse strict v1 Deck Text, accepting CRLF and unpadded card numbers."""

    if text.startswith("\ufeff"):
        raise DeckTextError("UTF-8 BOM is not part of Deck Text v1")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != HEADER:
        raise DeckTextError("first line must be '# PTCGP-DECK 1'")

    name: str | None = None
    energies: tuple[str, ...] | None = None
    sections: dict[Section, list[DeckCard]] = {"pokemon": [], "trainer": []}
    current: Section | None = None
    seen_sections: set[Section] = set()
    seen_metadata: set[str] = set()

    for line_number, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        if line == "[pokemon]" or line == "[trainer]":
            section = cast(Section, line[1:-1])
            if energies is None:
                raise DeckTextError(f"line {line_number}: energy must precede sections")
            if section in seen_sections:
                raise DeckTextError(f"line {line_number}: duplicate section {line}")
            if section == "trainer" and "pokemon" not in seen_sections:
                raise DeckTextError(f"line {line_number}: [pokemon] must precede [trainer]")
            seen_sections.add(section)
            current = section
            continue
        if line.startswith("name:"):
            if current is not None:
                raise DeckTextError(f"line {line_number}: metadata must precede sections")
            if energies is not None:
                raise DeckTextError(f"line {line_number}: name must precede energy")
            if "name" in seen_metadata:
                raise DeckTextError(f"line {line_number}: duplicate name field")
            value = line[5:]
            if not value.startswith(" ") or not value[1:].strip():
                raise DeckTextError(f"line {line_number}: invalid name field")
            name = value[1:].strip()
            if name != value[1:]:
                raise DeckTextError(f"line {line_number}: name has surrounding whitespace")
            seen_metadata.add("name")
            continue
        if line.startswith("energy:"):
            if current is not None:
                raise DeckTextError(f"line {line_number}: metadata must precede sections")
            if "energy" in seen_metadata:
                raise DeckTextError(f"line {line_number}: duplicate energy field")
            value = line[7:]
            if not value.startswith(" ") or not value[1:].strip():
                raise DeckTextError(f"line {line_number}: invalid energy field")
            raw_energies = tuple(part.strip().lower() for part in value[1:].split(","))
            if any(not item for item in raw_energies):
                raise DeckTextError(f"line {line_number}: empty energy value")
            if any(item not in ALLOWED_ENERGIES for item in raw_energies):
                raise DeckTextError(f"line {line_number}: unknown energy")
            if len(set(raw_energies)) != len(raw_energies):
                raise DeckTextError(f"line {line_number}: duplicate energy")
            energies = raw_energies
            seen_metadata.add("energy")
            continue
        if current is None:
            raise DeckTextError(f"line {line_number}: expected metadata or section")
        match = _CARD_LINE.fullmatch(line)
        if match is None:
            raise DeckTextError(f"line {line_number}: invalid card line")
        card_name = match.group("name")
        if card_name != card_name.strip():
            raise DeckTextError(f"line {line_number}: card name has surrounding whitespace")
        card = DeckCard(
            ref=CardRef(match.group("set"), int(match.group("number"))),
            name=card_name,
            count=int(match.group("count")),
            section=current,
        )
        sections[current].append(card)

    if energies is None:
        raise DeckTextError("missing energy field")
    if seen_sections != {"pokemon", "trainer"}:
        raise DeckTextError("both [pokemon] and [trainer] sections are required")
    return Deck(
        name=name,
        energies=energies,
        pokemon=tuple(sections["pokemon"]),
        trainer=tuple(sections["trainer"]),
    )


def read_deck_text(path: str | Path) -> Deck:
    """Read and parse a UTF-8 Deck Text file."""

    return parse_deck_text(Path(path).read_text(encoding="utf-8"))
