from __future__ import annotations

from pathlib import Path

import pytest

from ptcgp_deck2qr.decktext import (
    CardRef,
    Deck,
    DeckCard,
    DeckTextError,
    DeckValidationError,
    canonicalize_deck,
    parse_deck_text,
    validate_deck,
    write_deck_text,
)
from ptcgp_deck2qr.decktext.parser import read_deck_text


def _deck() -> Deck:
    return Deck(
        name="synthetic",
        energies=("lightning",),
        pokemon=(
            DeckCard(CardRef("A1", 2), "Beta", 1, "pokemon"),
            DeckCard(CardRef("A1", 1), "Alpha", 2, "pokemon"),
            DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),
        ),
        trainer=(DeckCard(CardRef("A1", 3), "Trainer", 2, "trainer"),),
    )


def test_writer_aggregates_and_round_trips() -> None:
    deck = _deck()
    text = write_deck_text(deck)
    assert text.endswith("\n")
    assert "energy: lightning\n" in text
    assert "energy: lightning, " not in text
    assert text.encode("utf-8") == (
        b"# PTCGP-DECK 1\nname: synthetic\nenergy: lightning\n\n"
        b"[pokemon]\n3 Alpha | A1-001\n1 Beta | A1-002\n\n"
        b"[trainer]\n2 Trainer | A1-003\n"
    )
    assert text == write_deck_text(parse_deck_text(text))
    assert "3 Alpha | A1-001" in text
    assert "2 Trainer | A1-003" in text


def test_parser_accepts_crlf_and_unpadded_numbers() -> None:
    text = (
        "# PTCGP-DECK 1\r\nenergy: FIRE, lightning\r\n\r\n[pokemon]\r\n"
        "1 Alpha | A1-1\r\n\r\n[trainer]\r\n"
    )
    deck = parse_deck_text(text)
    assert deck.energies == ("fire", "lightning")
    assert deck.pokemon[0].ref.print_id == "A1-001"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# PTCGP-DECK 2\nenergy: fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire,\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\n1 Bad line\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\n[trainer]\n[trainer]\n",
    ],
)
def test_parser_rejects_invalid_documents(text: str) -> None:
    with pytest.raises(DeckTextError):
        parse_deck_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "\ufeff# PTCGP-DECK 1\nenergy: fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nname: bad \nenergy: fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nname:\nenergy: fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nname: first\nname: second\nenergy: fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\nname: late\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy:fire\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\nenergy: water\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\nenergy: water\n[trainer]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\n[trainer]\n1  Alpha | A1-1\n",
        "# PTCGP-DECK 1\nenergy: fire\n[pokemon]\n1 Alpha | A1-1\n",
        "# PTCGP-DECK 1\nname: deck\nenergy: fire\n[pokemon]\n[trainer]\nunknown: x\n",
    ],
)
def test_parser_rejects_specific_strictness_violations(text: str) -> None:
    with pytest.raises(DeckTextError):
        parse_deck_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "# PTCGP-DECK 1\nenergy: fire\nname: late\n[pokemon]\n[trainer]\n",
        "# PTCGP-DECK 1\n[trainer]\nenergy: fire\n[pokemon]\n",
        "# PTCGP-DECK 1\nenergy: fire\n[trainer]\n[pokemon]\n",
    ],
)
def test_parser_enforces_v1_metadata_and_section_order(text: str) -> None:
    with pytest.raises(DeckTextError):
        parse_deck_text(text)


def test_read_deck_text_reads_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "deck.txt"
    path.write_text(write_deck_text(_deck()), encoding="utf-8")
    assert read_deck_text(path).name == "synthetic"


def test_card_ref_and_card_validation_reject_bad_values() -> None:
    with pytest.raises(ValueError):
        CardRef("bad code!", 1)
    with pytest.raises(ValueError):
        CardRef("A1", 0)
    with pytest.raises(ValueError):
        DeckCard(CardRef("A1", 1), "", 1, "pokemon")
    with pytest.raises(ValueError):
        DeckCard(CardRef("A1", 1), "Alpha", 0, "pokemon")


def test_validation_catches_game_invariants() -> None:
    small = Deck(
        energies=("lightning",),
        pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),),
        trainer=(DeckCard(CardRef("A1", 3), "Trainer", 1, "trainer"),),
    )
    with pytest.raises(DeckValidationError, match="exactly 20"):
        validate_deck(small)
    with pytest.raises(DeckValidationError, match="unknown energies"):
        validate_deck(Deck(energies=("dragon",), pokemon=small.pokemon, trainer=small.trainer))
    with pytest.raises(DeckValidationError, match="unique"):
        validate_deck(
            Deck(
                energies=("fire", "fire"),
                pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),),
            ),
            require_twenty=False,
        )
    with pytest.raises(DeckValidationError, match="one to three"):
        validate_deck(Deck(energies=(), pokemon=_deck().pokemon), require_twenty=False)
    with pytest.raises(DeckValidationError, match="1 or 2"):
        validate_deck(
            Deck(
                energies=("fire",),
                pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 3, "pokemon"),),
            ),
            require_twenty=False,
        )
    with pytest.raises(DeckValidationError, match="at least one"):
        validate_deck(Deck(energies=("fire",), trainer=small.trainer), require_twenty=False)


def test_validation_resolver_and_cross_section_checks() -> None:
    class Print:
        def __init__(self, section: str) -> None:
            self.section = section

    class Resolver:
        def resolve_print(self, set_code: str, number: int) -> Print | None:
            return None if number == 9 else Print("pokemon")

    with pytest.raises(DeckValidationError, match="both sections"):
        validate_deck(
            Deck(
                energies=("fire",),
                pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),),
                trainer=(DeckCard(CardRef("A1", 1), "Alpha", 1, "trainer"),),
            ),
            require_twenty=False,
        )
    with pytest.raises(DeckValidationError, match="unknown print"):
        validate_deck(
            Deck(
                energies=("fire",),
                pokemon=(DeckCard(CardRef("A1", 9), "Unknown", 1, "pokemon"),),
            ),
            resolver=Resolver(),
            require_twenty=False,
        )


def test_validation_resolver_checks_database_section() -> None:
    class Print:
        section = "trainer"

    class Resolver:
        def resolve_print(self, set_code: str, number: int) -> Print:
            return Print()

    deck = Deck(
        energies=("fire",),
        pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),),
    )
    with pytest.raises(DeckValidationError, match="section mismatch"):
        validate_deck(deck, resolver=Resolver(), require_twenty=False)


def test_canonicalize_rejects_conflicts_and_cross_section_duplicates() -> None:
    conflict = Deck(
        energies=("fire",),
        pokemon=(DeckCard(CardRef("A1", 1), "Alpha", 1, "pokemon"),),
        trainer=(DeckCard(CardRef("A1", 1), "Other", 1, "trainer"),),
    )
    with pytest.raises(ValueError):
        canonicalize_deck(conflict)
