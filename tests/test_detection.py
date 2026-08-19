from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from ptcgp_deck2qr.detection import (
    BoundingBox,
    CountObservation,
    DetectedRegion,
    detect_regions,
    extract_count,
)
from ptcgp_deck2qr.detection.counts import (
    _normalize_glyph,
    _overlap_score,
    _recognize_digit,
    _select_count_text_observation,
)

from .helpers import make_screenshot


def test_separate_card_grid_detection(tmp_path: Path) -> None:
    image_path = tmp_path / "grid.png"
    make_screenshot(image_path)
    image = cv2.imread(str(image_path))
    assert image is not None
    result = detect_regions(image, "auto")
    assert result.style == "separate-cards"
    assert len(result.regions) == 20
    assert extract_count(image, result.regions[0]).count == 1


def test_badge_grid_regularization_and_count_failure() -> None:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    region = DetectedRegion(
        index=1,
        bbox=BoundingBox(0, 0, 120, 170),
        detection_score=1.0,
        crop_quality=1.0,
        style="count-badge",
        row=0,
        column=0,
    )
    observation = extract_count(image, region)
    assert observation.count is None
    assert observation.reason in {"digit-not-found", "digit-ambiguous", "digit-shape-invalid"}


def test_count_templates_cover_1_2_polarities_and_failures() -> None:
    for digit, light_on_dark in ((1, False), (2, False), (1, True), (2, True)):
        background = 0 if light_on_dark else 255
        foreground = 255 if light_on_dark else 0
        image = np.full((50, 40, 3), background, dtype=np.uint8)
        cv2.putText(
            image,
            str(digit),
            (8, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (foreground, foreground, foreground),
            2,
            cv2.LINE_AA,
        )
        result = _recognize_digit(image, light_on_dark=light_on_dark)
        assert result.count == digit
    assert _recognize_digit(np.empty((0, 0, 3), dtype=np.uint8), light_on_dark=False).reason == (
        "empty-count-region"
    )
    assert _recognize_digit(np.full((20, 20), 255, dtype=np.uint8), light_on_dark=False).reason == (
        "digit-not-found"
    )
    assert _overlap_score(np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2), dtype=np.uint8)) == 0
    assert _normalize_glyph(np.zeros((2, 2), dtype=np.uint8)).shape == (32, 24)


def test_count_text_and_quantity_paths_are_region_bound() -> None:
    image = np.full((250, 150, 3), 255, dtype=np.uint8)
    cv2.putText(image, "1", (55, 215), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
    region = DetectedRegion(1, BoundingBox(10, 10, 120, 170), 1.0, 1.0, "count-text", 0, 0)
    assert extract_count(image, region).method == "count-text"
    quantity = DetectedRegion(1, region.bbox, 1.0, 1.0, "quantity-label", 0, 0)
    assert extract_count(image, quantity).method == "quantity"
    unknown = DetectedRegion(1, region.bbox, 1.0, 1.0, "auto", 0, 0)
    assert extract_count(image, unknown, style="auto").reason == "unsupported-style"


def test_count_text_inline_consensus_beats_broad_view_clutter() -> None:
    selected = _select_count_text_observation(
        (
            CountObservation(2, 0.66, "template"),
            CountObservation(2, 0.69, "template"),
            CountObservation(1, 0.74, "template"),
        )
    )

    assert selected.count == 2
    assert selected.confidence == 0.66


def test_count_text_conflicting_inline_views_fail_closed() -> None:
    selected = _select_count_text_observation(
        (
            CountObservation(1, 0.72, "template"),
            CountObservation(2, 0.76, "template"),
            CountObservation(2, 0.91, "template"),
        )
    )

    assert selected.count is None
    assert selected.confidence == 0.49
    assert selected.reason == "digit-evidence-conflict"


def test_count_text_single_inline_evidence_beats_broad_clutter() -> None:
    selected = _select_count_text_observation(
        (
            CountObservation(2, 0.64, "template"),
            CountObservation(None, 0.44, "template", "digit-ambiguous"),
            CountObservation(1, 0.92, "template"),
        )
    )

    assert selected.count == 2
    assert selected.confidence == 0.64


def test_extract_count_preserves_conflict_and_guards_reverse_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = np.zeros((260, 260, 3), dtype=np.uint8)
    region = DetectedRegion(
        1,
        BoundingBox(20, 20, 120, 170),
        1.0,
        1.0,
        "count-text",
        0,
        0,
    )
    calls: list[dict[str, bool]] = []
    responses = iter(
        (
            CountObservation(1, 0.72, "template"),
            CountObservation(2, 0.76, "template"),
            CountObservation(2, 0.91, "template"),
            CountObservation(1, 0.99, "template"),
        )
    )

    def fake_recognize_digit(_image: object, **options: bool) -> CountObservation:
        calls.append(options)
        return next(responses)

    monkeypatch.setattr(
        "ptcgp_deck2qr.detection.counts._recognize_digit",
        fake_recognize_digit,
    )

    observation = extract_count(image, region)

    assert observation.count is None
    assert observation.reason == "digit-evidence-conflict"
    # The fourth response represents an otherwise-accepted reverse-polarity
    # fallback.  A conflict is terminal, so it must never be requested.
    assert len(calls) == 3
    assert calls[0]["require_suffix_marker"] is True
    assert calls[1]["require_suffix_marker"] is True

    single_calls: list[dict[str, bool]] = []
    single_responses = iter(
        (
            CountObservation(2, 0.64, "template"),
            CountObservation(None, 0.44, "template", "digit-ambiguous"),
            CountObservation(1, 0.92, "template"),
        )
    )

    def fake_single_inline(_image: object, **options: bool) -> CountObservation:
        single_calls.append(options)
        return next(single_responses)

    monkeypatch.setattr(
        "ptcgp_deck2qr.detection.counts._recognize_digit",
        fake_single_inline,
    )
    single = extract_count(image, region)

    assert single.count == 2
    assert single.confidence == 0.64
    assert len(single_calls) == 3

    fallback_calls: list[dict[str, bool]] = []
    fallback_responses = iter(
        (
            CountObservation(None, 0.2, "template", "digit-not-found"),
            CountObservation(None, 0.2, "template", "digit-not-found"),
            CountObservation(None, 0.2, "template", "digit-not-found"),
            CountObservation(2, 0.8, "template"),
        )
    )

    def fake_fallback(_image: object, **options: bool) -> CountObservation:
        fallback_calls.append(options)
        return next(fallback_responses)

    monkeypatch.setattr("ptcgp_deck2qr.detection.counts._recognize_digit", fake_fallback)
    fallback = extract_count(image, region)

    assert fallback.count == 2
    assert len(fallback_calls) == 4
    assert fallback_calls[-1]["light_on_dark"] is False
    assert fallback_calls[-1]["require_suffix_marker"] is True


def test_count_text_ignores_tiny_rule_below_inline_suffix() -> None:
    image = np.full((360, 340, 3), (10, 18, 28), dtype=np.uint8)
    box = BoundingBox(40, 20, 150, 210)
    cv2.putText(
        image,
        "Label",
        (box.x + 4, box.bottom + 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 120, 60),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        "x2",
        (box.x + 85, box.bottom + 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 120, 60),
        2,
        cv2.LINE_AA,
    )
    # A small antialiased rule in the broad wrapped-label ROI used to become
    # a high-scoring "1" after size-normalization.
    cv2.line(
        image,
        (box.x + 145, box.bottom + 76),
        (box.x + 145, box.bottom + 83),
        (255, 120, 60),
        2,
        cv2.LINE_AA,
    )
    region = DetectedRegion(1, box, 1.0, 1.0, "count-text", 0, 0)

    observation = extract_count(image, region)

    assert observation.count == 2
    assert observation.method == "count-text"

    tiny_rule = np.zeros((88, 222, 3), dtype=np.uint8)
    cv2.line(tiny_rule, (145, 80), (145, 83), (255, 255, 255), 1, cv2.LINE_AA)
    rejected = _recognize_digit(tiny_rule, light_on_dark=True, prefer_bottom=True)
    assert rejected.count is None
    assert rejected.reason == "digit-shape-invalid"


def test_invalid_image_is_fail_closed() -> None:
    result = detect_regions(np.zeros((5, 5, 3), dtype=np.uint8))
    assert result.regions == ()
    assert result.errors == ("invalid-image",)
