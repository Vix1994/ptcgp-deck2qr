"""Normalized card database identities and source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

EntityType = Literal["pokemon", "trainer"]


@dataclass(frozen=True, slots=True, order=True)
class CardPrintKey:
    """Normalized upstream ``(set, number)`` print identity."""

    set_code: str
    number: int

    @property
    def print_id(self) -> str:
        return f"{self.set_code}-{self.number:03d}"


@dataclass(frozen=True, slots=True, order=True)
class CardEntityKey:
    """Semantic game entity parsed from an upstream visual filename."""

    entity_type: EntityType
    number: int

    @property
    def code(self) -> str:
        return f"{'PK' if self.entity_type == 'pokemon' else 'TR'}:{self.number}"


@dataclass(frozen=True, slots=True, order=True)
class CardPrint:
    """One set/number print and its visual/entity mappings."""

    set_code: str
    number: int
    name: str
    rarity: str
    image: str
    image_path: Path
    entity: CardEntityKey
    release_date: date
    release_order: int
    packs: tuple[str, ...] = ()

    @property
    def key(self) -> CardPrintKey:
        return CardPrintKey(self.set_code, self.number)

    @property
    def print_id(self) -> str:
        return f"{self.set_code}-{self.number:03d}"

    @property
    def section(self) -> EntityType:
        return self.entity.entity_type


@dataclass(frozen=True, slots=True)
class CardVisual:
    """One unique upstream image asset and all print aliases."""

    visual_id: str
    image_path: Path
    entity: CardEntityKey
    print_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceManifest:
    """Hash and schema facts used to validate generated indexes."""

    schema_version: int
    cards_sha256: str
    sets_sha256: str
    card_count: int
    visual_count: int
    source_name: str = "pokemon-tcg-pocket-database"
    source_version: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "cards_sha256": self.cards_sha256,
            "sets_sha256": self.sets_sha256,
            "card_count": self.card_count,
            "visual_count": self.visual_count,
            "source_name": self.source_name,
            "source_version": self.source_version,
        }
