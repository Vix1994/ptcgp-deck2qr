"""Convert a validated Deck into the database identities used by the QR encoder."""

from __future__ import annotations

from dataclasses import dataclass

from ..carddb import CardDatabase
from ..carddb.models import CardEntityKey
from ..decktext import Deck, validate_deck


class QrInputError(ValueError):
    """Raised when a validated Deck cannot be mapped to QR identities."""


@dataclass(frozen=True, slots=True)
class QrCardInput:
    """One aggregated Deck card and its upstream image identity."""

    print_id: str
    image: str
    count: int

    def to_dict(self) -> dict[str, object]:
        return {"print_id": self.print_id, "image": self.image, "count": self.count}


@dataclass(frozen=True, slots=True)
class QrInput:
    """Browser-safe input for the pinned deck-code encoder."""

    name: str
    energies: tuple[str, ...]
    cards: tuple[QrCardInput, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "energies": list(self.energies),
            "cards": [card.to_dict() for card in self.cards],
        }


def build_qr_input(deck: Deck, database: CardDatabase) -> QrInput:
    """Resolve a complete Deck through the active database and fail closed."""

    validate_deck(deck, resolver=database)
    entity_counts: dict[CardEntityKey, int] = {}
    cards: list[QrCardInput] = []
    for card in deck.cards:
        resolved = database.resolve_print(card.set_code, card.number)
        if resolved is None:  # Defensive even though ``validate_deck`` checks this.
            raise QrInputError(f"QR mapping is missing {card.ref.print_id}")
        if resolved.entity.number % 10 != 0:
            raise QrInputError(
                f"QR identity is not divisible by ten for {card.ref.print_id}: {resolved.image}"
            )
        combined = entity_counts.get(resolved.entity, 0) + card.count
        if combined > 2:
            raise QrInputError(f"QR entity count exceeds two for {card.ref.print_id}")
        entity_counts[resolved.entity] = combined
        cards.append(QrCardInput(card.ref.print_id, resolved.image, card.count))

    return QrInput(deck.name or "ptcgp-deck", deck.energies, tuple(cards))
