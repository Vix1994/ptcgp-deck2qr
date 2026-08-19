"""Canonical writer for Deck Text Format v1."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .model import CardRef, Deck, DeckCard, Section


def canonicalize_deck(
    deck: Deck,
    *,
    release_order: Mapping[str, int] | None = None,
) -> Deck:
    """Aggregate duplicate rows and return deterministic section ordering."""

    order = release_order or {}
    grouped: dict[Section, dict[CardRef, DeckCard]] = {"pokemon": {}, "trainer": {}}
    for card in deck.cards:
        existing = grouped[card.section].get(card.ref)
        if existing is None:
            grouped[card.section][card.ref] = card
        else:
            if existing.name != card.name:
                raise ValueError(f"conflicting names for {card.ref.print_id}")
            grouped[card.section][card.ref] = DeckCard(
                ref=card.ref,
                name=existing.name,
                count=existing.count + card.count,
                section=card.section,
            )
    if set(grouped["pokemon"]) & set(grouped["trainer"]):
        raise ValueError("a print cannot appear in both deck sections")

    def sort_key(card: DeckCard) -> tuple[int, str, int]:
        return (order.get(card.set_code, 10**9), card.set_code, card.number)

    return Deck(
        name=deck.name,
        energies=tuple(energy.lower() for energy in deck.energies),
        pokemon=tuple(sorted(grouped["pokemon"].values(), key=sort_key)),
        trainer=tuple(sorted(grouped["trainer"].values(), key=sort_key)),
    )


def write_deck_text(
    deck: Deck,
    *,
    release_order: Mapping[str, int] | None = None,
) -> str:
    """Serialize a Deck to canonical UTF-8 text with exactly one final LF."""

    canonical = canonicalize_deck(deck, release_order=release_order)
    lines = ["# PTCGP-DECK 1"]
    if canonical.name is not None:
        lines.append(f"name: {canonical.name}")
    lines.append(f"energy: {','.join(canonical.energies)}")
    lines.append("")
    lines.append("[pokemon]")
    lines.extend(_card_line(card) for card in canonical.pokemon)
    lines.append("")
    lines.append("[trainer]")
    lines.extend(_card_line(card) for card in canonical.trainer)
    return "\n".join(lines).rstrip("\n") + "\n"


def _card_line(card: DeckCard) -> str:
    return f"{card.count} {card.name} | {card.ref.print_id}"


def write_deck_file(
    deck: Deck,
    path: str | Path,
    *,
    release_order: Mapping[str, int] | None = None,
) -> None:
    """Write canonical Deck Text using UTF-8 and LF newlines."""

    Path(path).write_text(
        write_deck_text(deck, release_order=release_order), encoding="utf-8", newline="\n"
    )
