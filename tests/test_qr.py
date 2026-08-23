from __future__ import annotations

from pathlib import Path

import pytest

from ptcgp_deck2qr.carddb import load_database
from ptcgp_deck2qr.decktext import CardRef, Deck, DeckCard
from ptcgp_deck2qr.qr import QrInputError, build_qr_input

from .helpers import make_database


def make_deck(*, count: int = 2) -> Deck:
    pokemon = tuple(
        DeckCard(CardRef("A1", number), f"Synthetic Card {number}", count, "pokemon")
        for number in range(1, 6)
    )
    trainer = tuple(
        DeckCard(CardRef("A1", number), f"Synthetic Card {number}", count, "trainer")
        for number in range(6, 11)
    )
    return Deck(("lightning",), pokemon, trainer, "Synthetic Deck")


def make_incomplete_deck(*, missing: int) -> Deck:
    deck = make_deck()
    pokemon = tuple(
        DeckCard(card.ref, card.name, 1 if index < missing else 2, card.section)
        for index, card in enumerate(deck.pokemon)
    )
    return Deck(deck.energies, pokemon, deck.trainer, deck.name)


def test_qr_input_resolves_validated_deck_through_database(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=10))
    qr_input = build_qr_input(make_deck(), database)

    assert qr_input.name == "Synthetic Deck"
    assert qr_input.energies == ("lightning",)
    assert len(qr_input.cards) == 10
    assert sum(card.count for card in qr_input.cards) == 20
    assert qr_input.cards[0].to_dict() == {
        "print_id": "A1-001",
        "image": "cPK_10_000010_00_SYNTH_1_C.webp",
        "count": 2,
    }
    assert qr_input.to_dict()["energies"] == ["lightning"]
    assert qr_input.to_dict()["allow_incomplete"] is False


def test_qr_input_rejects_incomplete_deck(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=10))
    with pytest.raises(ValueError, match="exactly 20"):
        build_qr_input(make_deck(count=1), database)


@pytest.mark.parametrize("missing", [1, 2])
def test_qr_input_allows_explicit_incomplete_draft(tmp_path: Path, missing: int) -> None:
    database = load_database(make_database(tmp_path, count=10))
    qr_input = build_qr_input(
        make_incomplete_deck(missing=missing), database, allow_incomplete=True
    )

    assert sum(card.count for card in qr_input.cards) == 20 - missing
    assert qr_input.to_dict()["allow_incomplete"] is True


def test_qr_input_rejects_draft_below_eighteen_cards(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=10))
    with pytest.raises(QrInputError, match="18 to 20"):
        build_qr_input(make_deck(count=1), database, allow_incomplete=True)


def test_qr_input_rejects_non_deck_builder_identity(tmp_path: Path) -> None:
    database_path = make_database(tmp_path, count=10)
    cards_path = database_path / "cards.json"
    raw = cards_path.read_text(encoding="utf-8").replace("000010", "000011", 1)
    cards_path.write_text(raw, encoding="utf-8")
    database = load_database(database_path)
    with pytest.raises(QrInputError, match="not divisible by ten"):
        build_qr_input(make_deck(), database)
