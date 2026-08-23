from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from ptcgp_deck2qr.carddb import load_database
from ptcgp_deck2qr.carddb.errors import IndexSourceMismatch
from ptcgp_deck2qr.detection import BoundingBox, CountObservation, DetectedRegion, DetectionResult
from ptcgp_deck2qr.matching import MatchCandidate, MatchPolicy, MatchResult
from ptcgp_deck2qr.pipeline import (
    RecognitionCard,
    RecognitionResult,
    _build_deck,
    _canonical_print,
    _card_json,
    _make_result,
    _parse_energy,
    _write_annotated_image,
    recognize_image,
)

from .helpers import (
    make_badge_screenshot,
    make_count_text_screenshot,
    make_database,
    make_quantity_screenshot,
    make_screenshot,
)


def test_pipeline_emits_canonical_text_and_debug_artifacts(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image, card_count=10)
    result = recognize_image(
        image,
        energy="lightning",
        database_path=database,
        output_dir=tmp_path / "output",
        style="separate-cards",
    )
    assert result.accepted
    assert result.deck is not None and result.deck.total_count == 20
    output = tmp_path / "output"
    assert (output / "deck.txt").is_file()
    assert (output / "recognition.json").is_file()
    assert (output / "recognized.png").is_file()
    report = json.loads((output / "recognition.json").read_text(encoding="utf-8"))
    assert report["validation"]["accepted"] is True
    assert report["validation"]["card_count"] == 20
    first = report["cards"][0]
    assert first["selected_print"]
    assert "visual_score" in first and "entity_margin" in first
    assert "count_confidence" in first
    assert first["match_policy"]["name"] == "full-card-v1"
    assert report["match_policies"]["full-card-v1"]["min_score"] == 0.68
    assert report["proposals"]
    assert len(report["slots"]) == len(report["cards"])
    assert report["slots"][0]["slot_id"] == first["slot_id"]
    assert report["slots"][0]["proposal_ids"] == first["proposal_ids"]


@pytest.mark.parametrize(
    ("builder", "expected_style", "expected_regions"),
    [
        (make_screenshot, "separate-cards", 20),
        (make_quantity_screenshot, "quantity-label", 10),
        (make_count_text_screenshot, "count-text", 10),
        (make_badge_screenshot, "count-badge", 10),
    ],
)
def test_pipeline_auto_handles_all_supported_screenshot_styles(
    tmp_path: Path, builder: Callable[[Path], None], expected_style: str, expected_regions: int
) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / f"{expected_style}.png"
    builder(image)
    result = recognize_image(
        image,
        energy="fire",
        database_path=database,
        output_dir=tmp_path / f"{expected_style}-output",
        style="auto",
    )
    assert result.accepted
    assert result.detection.style == expected_style
    assert len(result.detection.regions) == expected_regions
    assert result.deck is not None and result.deck.total_count == 20
    assert all(card.count.count in (1, 2) for card in result.cards)
    report = json.loads(
        (tmp_path / f"{expected_style}-output" / "recognition.json").read_text(encoding="utf-8")
    )
    expected_policy = {
        "separate-cards": "full-card-v1",
        "quantity-label": "quantity-artwork-strict-v1",
        "count-text": "full-card-v1",
        "count-badge": "count-badge-strict-v1",
    }[expected_style]
    assert {card["match_policy"]["name"] for card in report["cards"]} == {expected_policy}


def test_pipeline_rejects_wrong_total_but_keeps_diagnostics(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image, copies=17, card_count=10)
    result = recognize_image(
        image,
        energy="fire",
        database_path=database,
        output_dir=tmp_path / "output",
        style="separate-cards",
    )
    assert not result.accepted
    assert result.draft_deck is None
    assert not (tmp_path / "output" / "deck.txt").exists()
    assert (tmp_path / "output" / "deck.partial.txt").exists()
    assert (tmp_path / "output" / "recognized.png").exists()


@pytest.mark.parametrize("copies", [18, 19])
def test_pipeline_builds_incomplete_draft(tmp_path: Path, copies: int) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image, copies=copies, card_count=10)

    result = recognize_image(
        image,
        energy="fire",
        database_path=database,
        output_dir=tmp_path / "output",
        style="separate-cards",
    )

    assert not result.accepted
    assert result.draft_deck is not None and result.draft_deck.total_count == copies
    assert result.deck is not None and result.deck.total_count == copies
    assert not (tmp_path / "output" / "deck.txt").exists()
    assert (tmp_path / "output" / "deck.partial.txt").exists()
    report = json.loads((tmp_path / "output" / "recognition.json").read_text(encoding="utf-8"))
    assert report["validation"]["card_count"] == copies
    assert report["validation"]["missing_card_count"] == 20 - copies
    assert report["validation"]["draft_qr_available"] is True


def test_pipeline_builds_twenty_card_draft_from_ambiguous_top_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image, card_count=10)
    strict_policy = MatchPolicy("test-reject-all", min_score=1.1, min_entity_margin=1.1)
    monkeypatch.setattr(
        "ptcgp_deck2qr.pipeline.policy_for_style",
        lambda _style: strict_policy,
    )

    result = recognize_image(
        image,
        energy="lightning",
        database_path=database,
        output_dir=tmp_path / "output",
        style="separate-cards",
    )

    assert not result.accepted
    assert result.draft_deck is not None and result.draft_deck.total_count == 20
    assert result.deck is None
    assert "match-ambiguous-entity" in result.errors
    assert not (tmp_path / "output" / "deck.txt").exists()
    partial = (tmp_path / "output" / "deck.partial.txt").read_text(encoding="utf-8")
    assert sum(line.startswith("2 Synthetic Card ") for line in partial.splitlines()) == 10
    report = json.loads((tmp_path / "output" / "recognition.json").read_text(encoding="utf-8"))
    assert report["validation"] == {
        "accepted": False,
        "card_count": 20,
        "draft_qr_available": True,
        "errors": ["match-ambiguous-entity"],
        "missing_card_count": 0,
        "reliable_card_count": 0,
        "uncertain_entity_count": 20,
    }


def test_pipeline_cleans_only_known_stale_outputs_before_failure(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image, card_count=10)
    output = tmp_path / "output"
    assert recognize_image(
        image,
        energy="fire",
        database_path=database,
        output_dir=output,
        style="separate-cards",
    ).accepted
    keep = output / "keep.txt"
    keep.write_text("keep", encoding="utf-8")
    bad_image = tmp_path / "bad.png"
    make_screenshot(bad_image, copies=19, card_count=10)
    failed = recognize_image(
        bad_image,
        energy="fire",
        database_path=database,
        output_dir=output,
        style="separate-cards",
    )
    assert not failed.accepted
    assert not (output / "deck.txt").exists()
    assert (output / "deck.partial.txt").exists()
    assert keep.read_text(encoding="utf-8") == "keep"

    # A subsequent explicit-index failure also clears the replaceable partial
    # output without touching the unrelated file.
    with pytest.raises(IndexSourceMismatch, match="build-index"):
        recognize_image(
            image,
            energy="fire",
            database_path=database,
            output_dir=output,
            style="separate-cards",
            index_path=output / "does-not-exist.json",
        )
    # An explicit missing index is an actionable error and must not leave the
    # prior accepted deck behind.  No unrelated file is removed.
    assert not (output / "deck.txt").exists()
    assert not (output / "deck.partial.txt").exists()
    assert keep.read_text(encoding="utf-8") == "keep"


def test_pipeline_invalid_input_and_energy_validation(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=2)
    with np.testing.assert_raises(ValueError):
        _parse_energy("fire,fire")
    with np.testing.assert_raises(ValueError):
        _parse_energy("dragon")
    result = recognize_image(
        tmp_path / "missing.png",
        energy=("fire",),
        database_path=database,
        output_dir=tmp_path / "output",
        style="auto",
    )
    assert not result.accepted
    assert (tmp_path / "output" / "recognized.png").exists()


def test_pipeline_checks_image_before_building_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = make_database(tmp_path, count=2)

    def fail_if_index_built(*args: object, **kwargs: object) -> object:
        raise AssertionError("index should not be built for unreadable input")

    monkeypatch.setattr("ptcgp_deck2qr.pipeline._get_index", fail_if_index_built)
    result = recognize_image(
        tmp_path / "missing.png",
        energy="fire",
        database_path=database,
        output_dir=tmp_path / "output",
    )
    assert not result.accepted
    assert "input-image-unreadable" in result.errors


def test_pipeline_debug_branches_and_alias_selection(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=2)
    database_view = load_database(database)
    assert _canonical_print(("A1-001", "A1-999"), database_view) is not None
    assert _canonical_print(("A1-999",), database_view) is None
    region = DetectedRegion(1, BoundingBox(0, 0, 20, 20), 1.0, 1.0, "separate-cards", 0, 0)
    rejected = MatchResult(False, None, (), 0.0, 0.0, "no-candidates")
    card = RecognitionCard(region, rejected, CountObservation(None, 0.0, "template", "bad"))
    assert not card.accepted
    assert _build_deck((card,), ("fire",), database_view, "x") is None
    assert _card_json(card, database_view)["selected_print"] is None
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    debug_result = RecognitionResult(
        False,
        tmp_path,
        DetectionResult("separate-cards", 0.0, (region,), ("test",)),
        (card,),
        ("test",),
    )
    _write_annotated_image(image, debug_result, tmp_path / "red.png")
    assert (tmp_path / "red.png").exists()
    selected = MatchCandidate("x", ("A1-001",), "pokemon", 1, 1.0)
    accepted_match = MatchResult(True, selected, (selected,), 1.0, 1.0)
    accepted = RecognitionCard(region, accepted_match, CountObservation(1, 1.0, "instance"))
    assert accepted.accepted
    assert _build_deck((accepted,), ("fire",), database_view, "x") is not None
    alias = MatchCandidate("x", ("A1-002", "A1-001"), "pokemon", 1, 1.0)
    alias_card = RecognitionCard(
        region, MatchResult(True, alias, (alias,), 1.0, 1.0), CountObservation(1, 1.0, "instance")
    )
    assert _card_json(alias_card, database_view)["selected_print"] == "A1-001"


def test_pipeline_fails_closed_on_duplicate_slot_id(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=2))
    region = DetectedRegion(
        1,
        BoundingBox(0, 0, 20, 20),
        1.0,
        1.0,
        "separate-cards",
        0,
        0,
        slot_id="r01c01",
    )
    duplicate = DetectedRegion(
        2,
        BoundingBox(30, 0, 20, 20),
        1.0,
        1.0,
        "separate-cards",
        0,
        1,
        slot_id="r01c01",
    )
    rejected = MatchResult(False, None, (), 0.0, 0.0, "test")
    cards = (
        RecognitionCard(region, rejected, CountObservation(1, 1.0, "instance")),
        RecognitionCard(duplicate, rejected, CountObservation(1, 1.0, "instance")),
    )
    result, _ = _make_result(
        tmp_path / "input.png",
        tmp_path / "output",
        DetectionResult("separate-cards", 1.0, (region, duplicate)),
        cards,
        ("fire",),
        database,
    )
    assert not result.accepted
    assert "duplicate-slot-conflict" in result.errors
