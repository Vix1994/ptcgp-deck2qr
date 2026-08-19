"""Pure domain values for a PTCG Pocket deck."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

Section = Literal["pokemon", "trainer"]

ALLOWED_ENERGIES = frozenset(
    {
        "grass",
        "fire",
        "water",
        "lightning",
        "psychic",
        "fighting",
        "darkness",
        "metal",
    }
)

_SET_CODE = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"


class DeckValidationError(ValueError):
    """Raised when a Deck violates syntax-independent game invariants."""


class ResolvedPrint(Protocol):
    """Typed minimum of a database print exposed to deck validation."""

    # Keep the domain independent from ``carddb``.  A database adapter only
    # has to expose this string-like section value for semantic validation.
    @property
    def section(self) -> str:
        """Return the semantic Deck Text section for this print."""

        ...


class PrintResolver(Protocol):
    """Small protocol used to validate a print without importing carddb."""

    def resolve_print(self, set_code: str, number: int) -> ResolvedPrint | None:
        """Return a database row for a print, or ``None`` when it is unknown."""


@dataclass(frozen=True, slots=True, order=True)
class CardRef:
    """The stable Deck Text identity: a set code and numeric card number."""

    set_code: str
    number: int

    def __post_init__(self) -> None:
        if not re.fullmatch(_SET_CODE, self.set_code):
            raise ValueError(f"invalid set code: {self.set_code!r}")
        if self.number <= 0:
            raise ValueError("card number must be positive")

    @property
    def print_id(self) -> str:
        """Return the canonical ``SET-001`` representation."""

        return f"{self.set_code}-{self.number:03d}"


@dataclass(frozen=True, slots=True)
class DeckCard:
    """One aggregated card entry in a deck section."""

    ref: CardRef
    name: str
    count: int
    section: Section

    @property
    def set_code(self) -> str:
        return self.ref.set_code

    @property
    def number(self) -> int:
        return self.ref.number

    def __post_init__(self) -> None:
        if not self.name.strip() or self.name != self.name.strip():
            raise ValueError("card name must be non-empty and trimmed")
        if self.count <= 0:
            raise ValueError("card count must be positive")
        if self.section not in ("pokemon", "trainer"):
            raise ValueError(f"unknown deck section: {self.section!r}")


@dataclass(frozen=True, slots=True)
class Deck:
    """A complete deck independent of image, database, and QR concerns."""

    energies: tuple[str, ...]
    pokemon: tuple[DeckCard, ...] = ()
    trainer: tuple[DeckCard, ...] = ()
    name: str | None = None

    @property
    def cards(self) -> tuple[DeckCard, ...]:
        return self.pokemon + self.trainer

    @property
    def total_count(self) -> int:
        return sum(card.count for card in self.cards)


def validate_deck(
    deck: Deck,
    *,
    resolver: PrintResolver | None = None,
    require_twenty: bool = True,
) -> None:
    """Validate a deck and raise :class:`DeckValidationError` on any issue.

    Parsing and game-deck validation are intentionally separate.  Callers that
    only need to inspect a syntactically valid partial deck can pass
    ``require_twenty=False``.
    """

    energies = tuple(energy.lower() for energy in deck.energies)
    if not 1 <= len(energies) <= 3:
        raise DeckValidationError("a deck must contain one to three energies")
    if len(set(energies)) != len(energies):
        raise DeckValidationError("deck energies must be unique")
    unknown_energies = set(energies) - ALLOWED_ENERGIES
    if unknown_energies:
        raise DeckValidationError(f"unknown energies: {sorted(unknown_energies)}")

    seen: set[CardRef] = set()
    for card in deck.cards:
        if card.ref in seen:
            raise DeckValidationError(f"duplicate print id: {card.ref.print_id}")
        seen.add(card.ref)
        if card.count not in (1, 2):
            raise DeckValidationError(
                f"card count must be 1 or 2 for {card.ref.print_id}, got {card.count}"
            )
        if card.section == "pokemon" and card.ref in {item.ref for item in deck.trainer}:
            raise DeckValidationError(f"print appears in both sections: {card.ref.print_id}")
        if resolver is not None:
            resolved = resolver.resolve_print(card.set_code, card.number)
            if resolved is None:
                raise DeckValidationError(f"unknown print id: {card.ref.print_id}")
            if resolved.section != card.section:
                raise DeckValidationError(
                    f"print section mismatch for {card.ref.print_id}: "
                    f"database={resolved.section}, deck={card.section}"
                )

    if not deck.pokemon:
        raise DeckValidationError("a deck must contain at least one Pokémon")
    if require_twenty and deck.total_count != 20:
        raise DeckValidationError(f"deck must contain exactly 20 cards, got {deck.total_count}")
