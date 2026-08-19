from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ptcgp_deck2qr.carddb import load_database
from ptcgp_deck2qr.matching import build_fingerprint_index, match_crop, policy_for_style
from ptcgp_deck2qr.matching.matcher import _accept_match

from .helpers import make_database


def test_exact_visual_match_is_accepted(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=3))
    index = build_fingerprint_index(database)
    image = cv2.imread(str(database.visuals[0].image_path))
    assert image is not None
    result = match_crop(image, index)
    assert result.accepted
    assert result.selected is not None
    assert result.visual_score > 0.95


def test_ambiguous_or_empty_match_fails_closed(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=3))
    index = build_fingerprint_index(database)
    blank = np.full((170, 120, 3), 127, dtype=np.uint8)
    result = match_crop(blank, index, min_score=0.99, min_entity_margin=0.99)
    assert not result.accepted
    assert result.reason in {"visual-score-low", "entity-ambiguous"}


def test_aligned_artwork_features_match_derived_art_crop(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=4))
    index = build_fingerprint_index(database)
    card = cv2.imread(str(database.visuals[2].image_path))
    assert card is not None
    artwork = card[13:95, 10:110]
    result = match_crop(artwork, index, artwork=True)
    assert result.accepted
    assert result.selected is not None
    assert result.selected.visual_id == database.visuals[2].visual_id


def test_strong_visual_can_clear_small_but_nonzero_entity_margin(tmp_path: Path) -> None:
    database = load_database(make_database(tmp_path, count=3))
    index = build_fingerprint_index(database)
    image = cv2.imread(str(database.visuals[0].image_path))
    assert image is not None
    result = match_crop(image, index)
    assert result.accepted
    assert result.visual_score >= 0.94
    assert result.entity_margin >= 0.025


def test_dual_threshold_accepts_known_strong_margin_and_rejects_near_tie() -> None:
    assert _accept_match(0.9596, 0.0308, min_score=0.68, min_entity_margin=0.035)
    assert not _accept_match(0.95, 0.01, min_score=0.68, min_entity_margin=0.035)
    assert not _accept_match(0.995, 0.03, min_score=0.99, min_entity_margin=0.99)


def test_style_aware_policies_reject_known_partial_false_accepts() -> None:
    quantity = policy_for_style("quantity-label")
    assert quantity.name == "quantity-artwork-strict-v1"
    assert quantity.min_score > 0.738
    assert quantity.min_entity_margin > 0.052
    assert not _accept_match(
        0.738,
        0.052,
        min_score=quantity.min_score,
        min_entity_margin=quantity.min_entity_margin,
        allow_strong_override=quantity.allow_strong_override,
    )

    badge = policy_for_style("count-badge")
    assert badge.name == "count-badge-strict-v1"
    assert badge.min_score > 0.793
    assert badge.min_entity_margin > 0.051
    assert not _accept_match(
        0.793,
        0.051,
        min_score=badge.min_score,
        min_entity_margin=badge.min_entity_margin,
        allow_strong_override=badge.allow_strong_override,
    )


def test_full_card_policy_retains_evidence_backed_strong_match_override() -> None:
    full_card = policy_for_style("separate-cards")
    assert full_card.name == "full-card-v1"
    assert _accept_match(
        0.9596,
        0.0308,
        min_score=full_card.min_score,
        min_entity_margin=full_card.min_entity_margin,
        allow_strong_override=full_card.allow_strong_override,
        strong_score=full_card.strong_score,
        strong_margin=full_card.strong_margin,
    )
    assert policy_for_style("count-text") is full_card
