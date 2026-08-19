"""Restricted 1/2 quantity extraction with fail-closed decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .models import BoundingBox, CardSlot, StyleName

ImageArray = NDArray[Any]


@dataclass(frozen=True, slots=True)
class CountObservation:
    count: int | None
    confidence: float
    method: str
    reason: str | None = None


def extract_count(
    image: ImageArray,
    region: CardSlot,
    *,
    style: StyleName | None = None,
) -> CountObservation:
    """Extract only counts 1 and 2 from a region-bound local ROI."""

    actual_style = style or region.style
    if actual_style == "separate-cards":
        return CountObservation(1, 1.0, "instance")
    height, width = image.shape[:2]
    card = region.bbox.clamp(width, height)
    if actual_style == "count-badge":
        roi = BoundingBox(
            card.x + int(card.width * 0.55),
            card.y + int(card.height * 0.58),
            int(card.width * 0.75),
            int(card.height * 0.62),
        ).clamp(width, height)
        local = image[roi.y : roi.bottom, roi.x : roi.right]
        badge = _red_badge_crop(local)
        observation = _recognize_digit(badge if badge is not None else local, light_on_dark=True)
        return _with_method(observation, "badge")
    if actual_style in ("count-text", "quantity-label"):
        if actual_style == "quantity-label":
            roi = BoundingBox(
                card.x + int(card.width * 0.20),
                card.bottom,
                int(card.width * 0.60),
                int(card.height * 0.42),
            ).clamp(width, height)
            local = image[roi.y : roi.bottom, roi.x : roi.right]
            if local.shape[0] > 4:
                # The gray cell contains a name line followed by the numeral;
                # using the lower 42% avoids treating a letter in ``Quantity``
                # as a count glyph.
                local = local[int(local.shape[0] * 0.58) :, :]
            observation = _recognize_digit(local, light_on_dark=True)
            if observation.count is None:
                fallback = _recognize_digit(local, light_on_dark=False)
                if fallback.count is not None:
                    observation = fallback
            extended_roi = BoundingBox(
                card.x + int(card.width * 0.20),
                card.bottom,
                int(card.width * 0.60),
                int(card.height * 0.72),
            ).clamp(width, height)
            extended = _recognize_digit(
                image[extended_roi.y : extended_roi.bottom, extended_roi.x : extended_roi.right],
                light_on_dark=True,
                prefer_bottom=True,
            )
            if extended.count in (1, 2) and extended.confidence > observation.confidence:
                observation = extended
        else:
            # In the deck-list style the count is the right-most glyph in the
            # name/count line.  Three bounded ROIs cover regular labels,
            # labels that extend slightly past the detected card, and a
            # wrapped long name such as ``Professor's Research``.
            rois = (
                BoundingBox(
                    card.x + int(card.width * 0.55),
                    card.bottom,
                    int(card.width * 0.45),
                    int(card.height * 0.28),
                ),
                BoundingBox(
                    card.x + int(card.width * 0.68),
                    card.bottom,
                    int(card.width * 0.95),
                    int(card.height * 0.28),
                ),
                BoundingBox(
                    card.x + int(card.width * 0.12),
                    card.bottom,
                    int(card.width * 1.48),
                    int(card.height * 0.42),
                ),
            )
            observations: list[CountObservation] = []
            for index, raw_roi in enumerate(rois):
                roi = raw_roi.clamp(width, height)
                observations.append(
                    _recognize_digit(
                        image[roi.y : roi.bottom, roi.x : roi.right],
                        light_on_dark=True,
                        prefer_rightmost=index < 2,
                        prefer_bottom=index == 2,
                        require_suffix_marker=index < 2,
                    )
                )
            observation = _select_count_text_observation(tuple(observations))
            if observation.count is None and observation.reason != "digit-evidence-conflict":
                fallback_roi = rois[0].clamp(width, height)
                fallback = _recognize_digit(
                    image[
                        fallback_roi.y : fallback_roi.bottom, fallback_roi.x : fallback_roi.right
                    ],
                    light_on_dark=False,
                    prefer_rightmost=True,
                    require_suffix_marker=True,
                )
                if fallback.count is not None:
                    observation = fallback
        return _with_method(
            observation, "quantity" if actual_style == "quantity-label" else "count-text"
        )
    return CountObservation(None, 0.0, "unknown", "unsupported-style")


def _with_method(observation: CountObservation, method: str) -> CountObservation:
    return CountObservation(observation.count, observation.confidence, method, observation.reason)


def _select_count_text_observation(
    observations: tuple[CountObservation, ...],
) -> CountObservation:
    """Select count evidence without letting a broad fallback override consensus.

    The first two count-text views are tightly bound to the right-hand inline
    suffix.  The third view is intentionally broader so it can see a wrapped
    suffix, but it also contains more table borders and surrounding text.  Two
    accepted inline views agreeing on a digit are therefore stronger evidence
    than a single, slightly higher-scoring broad-view glyph.
    """

    if not observations:
        return CountObservation(None, 0.0, "template", "digit-not-found")
    inline = [item for item in observations[:2] if item.count in (1, 2)]
    if len(inline) == 2:
        confidence = min(item.confidence for item in inline)
        if inline[0].count == inline[1].count:
            return CountObservation(inline[0].count, confidence, "template")
        return CountObservation(
            None,
            min(0.49, confidence),
            "template",
            "digit-evidence-conflict",
        )
    if len(inline) == 1:
        return inline[0]
    broad = observations[2:]
    accepted_broad = [item for item in broad if item.count in (1, 2)]
    return max(accepted_broad or broad or observations, key=lambda item: item.confidence)


def _recognize_digit(
    image: ImageArray,
    *,
    light_on_dark: bool,
    prefer_rightmost: bool = False,
    prefer_bottom: bool = False,
    require_suffix_marker: bool = False,
) -> CountObservation:
    if image.size == 0:
        return CountObservation(None, 0.0, "template", "empty-count-region")
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    threshold_type = cv2.THRESH_BINARY if light_on_dark else cv2.THRESH_BINARY_INV
    _, binary = cv2.threshold(gray, 0, 255, threshold_type + cv2.THRESH_OTSU)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    components = _components(binary)
    if not components:
        return CountObservation(None, 0.0, "template", "digit-not-found")
    minimum_height = max(4, int(binary.shape[0] * 0.10)) if prefer_rightmost or prefer_bottom else 4
    valid_components = [
        component
        for component in components
        if component[0] >= 4
        and component[3] >= 2
        and component[4] >= minimum_height
        and component[3] <= max(12, int(binary.shape[1] * 0.48))
        and component[4] <= int(binary.shape[0] * 0.88)
    ]
    if not valid_components:
        return CountObservation(None, 0.0, "template", "digit-shape-invalid")
    scored: list[tuple[float, float, tuple[int, int, int, int, int]]] = []
    for component in valid_components:
        _, x, y, width, height = component
        glyph = binary[y : y + height, x : x + width]
        score_one = _template_score(glyph, 1)
        score_two = _template_score(glyph, 2)
        scored.append((max(score_one, score_two), abs(score_one - score_two), component))
    if require_suffix_marker:
        suffix_scored = [item for item in scored if _has_suffix_marker(binary, item[2], components)]
        suffix_scored.extend(
            candidate
            for component in valid_components
            if (candidate := _connected_suffix_candidate(binary, component)) is not None
        )
        if not suffix_scored:
            confidence = max((item[0] for item in scored), default=0.0)
            return CountObservation(
                None,
                min(0.49, confidence),
                "template",
                "digit-suffix-marker-not-found",
            )
        scored = suffix_scored
    if prefer_rightmost:
        rightmost = max(
            (item for item in scored if item[0] >= 0.28),
            key=lambda item: item[2][1] + item[2][3],
            default=None,
        )
        if rightmost is not None:
            scored = [rightmost]
    if prefer_bottom and scored:
        bottom_y = max(item[2][2] + item[2][4] for item in scored)
        bottom_candidates = [item for item in scored if bottom_y - (item[2][2] + item[2][4]) <= 8]
        scored = [max(bottom_candidates, key=lambda item: item[2][1] + item[2][3])]
    best, margin, _ = max(scored, key=lambda item: (item[0], item[1], item[2][0]))
    if best < 0.38 or margin < 0.035:
        return CountObservation(None, min(0.49, best), "template", "digit-ambiguous")
    selected_score = max(
        scored,
        key=lambda item: (item[0], item[1], item[2][0]),
    )
    _, _, (_, x, y, width, height) = selected_score
    glyph = binary[y : y + height, x : x + width]
    score_one = _template_score(glyph, 1)
    score_two = _template_score(glyph, 2)
    ratio = width / max(1, height)
    if abs(score_one - score_two) < 0.12 and ratio < 0.64:
        digit = 1
    elif abs(score_one - score_two) < 0.12 and ratio > 0.68:
        digit = 2
    else:
        digit = 1 if score_one > score_two else 2
    return CountObservation(digit, min(0.99, best), "template")


def _red_badge_crop(image: ImageArray) -> ImageArray | None:
    """Return the tightest red badge crop, excluding the card's white body."""

    if image.size == 0:
        return None
    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = (((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 90)).astype(
        np.uint8
    ) * 255
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    components = _components(closed_mask)
    candidates = [
        component
        for component in components
        if component[0] >= max(8, int(mask.size * 0.003))
        and component[3] >= 5
        and component[4] >= 5
    ]
    if not candidates:
        return None
    _, x, y, width, height = max(candidates, key=lambda item: item[0])
    padding = max(2, min(width, height) // 10)
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(bgr.shape[1], x + width + padding)
    bottom = min(bgr.shape[0], y + height + padding)
    return bgr[top:bottom, left:right]


def _components(binary: ImageArray) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)  # type: ignore[call-overload]
    return [
        (
            int(stats[index, cv2.CC_STAT_AREA]),
            int(stats[index, cv2.CC_STAT_LEFT]),
            int(stats[index, cv2.CC_STAT_TOP]),
            int(stats[index, cv2.CC_STAT_WIDTH]),
            int(stats[index, cv2.CC_STAT_HEIGHT]),
        )
        for index in range(1, count)
    ]


def _template_score(glyph: ImageArray, digit: int) -> float:
    templates: list[ImageArray] = []
    for scale in (0.7, 0.9, 1.1, 1.3):
        canvas = np.zeros((64, 48), dtype=np.uint8)
        cv2.putText(
            canvas, str(digit), (10, 50), cv2.FONT_HERSHEY_SIMPLEX, scale, 255, 2, cv2.LINE_AA
        )
        templates.append(canvas)
    candidate = _normalize_glyph(glyph)
    return max(_overlap_score(candidate, _normalize_glyph(template)) for template in templates)


def _has_suffix_marker(
    binary: ImageArray,
    digit: tuple[int, int, int, int, int],
    components: list[tuple[int, int, int, int, int]],
) -> bool:
    """Return whether a digit is immediately preceded by an x-like suffix marker."""

    _, digit_x, digit_y, _, digit_height = digit
    digit_center_y = digit_y + digit_height / 2.0
    maximum_gap = max(4, int(digit_height * 0.55))
    for marker in components:
        if marker == digit:
            continue
        area, x, y, width, height = marker
        gap = digit_x - (x + width)
        height_ratio = height / max(1, digit_height)
        aspect_ratio = width / max(1, height)
        center_delta = abs((y + height / 2.0) - digit_center_y)
        if (
            area >= 8
            and 0 <= gap <= maximum_gap
            and 0.45 <= height_ratio <= 0.85
            and 0.65 <= aspect_ratio <= 1.35
            and center_delta <= digit_height * 0.30
        ):
            glyph = binary[y : y + height, x : x + width]
            if _suffix_marker_score(glyph) >= 0.72:
                return True
    return False


def _suffix_marker_score(glyph: ImageArray) -> float:
    candidate = _normalize_glyph(glyph)
    scores: list[float] = []
    for marker in ("x", "X"):
        for scale in (0.7, 1.0, 1.3):
            for thickness in (1, 2, 3):
                canvas = np.zeros((64, 48), dtype=np.uint8)
                cv2.putText(
                    canvas,
                    marker,
                    (8, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    scale,
                    255,
                    thickness,
                    cv2.LINE_AA,
                )
                scores.append(_overlap_score(candidate, _normalize_glyph(canvas)))
    return max(scores, default=0.0)


def _connected_suffix_candidate(
    binary: ImageArray,
    component: tuple[int, int, int, int, int],
) -> tuple[float, float, tuple[int, int, int, int, int]] | None:
    """Split a small connected ``xN`` component into marker and digit evidence."""

    _, x, y, width, height = component
    aspect_ratio = width / max(1, height)
    if not 1.05 <= aspect_ratio <= 1.80 or width < 8:
        return None
    glyph = binary[y : y + height, x : x + width]
    projection = np.count_nonzero(glyph, axis=0)
    start = max(2, int(width * 0.30))
    stop = min(width - 2, int(width * 0.65))
    if stop < start:
        return None
    best: (
        tuple[
            float,
            float,
            tuple[int, int, int, int, int],
            float,
        ]
        | None
    ) = None
    maximum_projection = max(1, int(np.max(projection)))
    for split in range(start, stop + 1):
        valley_ratio = float(projection[split] / maximum_projection)
        if valley_ratio > 0.60:
            continue
        marker = glyph[:, :split]
        digit = glyph[:, split:]
        marker_score = _suffix_marker_score(marker)
        score_one = _template_score(digit, 1)
        score_two = _template_score(digit, 2)
        digit_score = max(score_one, score_two)
        margin = abs(score_one - score_two)
        digit_component = _tight_component(digit, x + split, y)
        if marker_score < 0.72 or digit_score < 0.38 or margin < 0.035 or digit_component is None:
            continue
        ranking = marker_score + digit_score + margin - valley_ratio * 0.20
        candidate = (digit_score, margin, digit_component, ranking)
        if best is None or candidate[3] > best[3]:
            best = candidate
    return (best[0], best[1], best[2]) if best is not None else None


def _tight_component(
    glyph: ImageArray,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int, int] | None:
    ys, xs = np.where(glyph > 0)
    if len(xs) == 0:
        return None
    left = int(np.min(xs))
    top = int(np.min(ys))
    right = int(np.max(xs)) + 1
    bottom = int(np.max(ys)) + 1
    return (
        len(xs),
        offset_x + left,
        offset_y + top,
        right - left,
        bottom - top,
    )


def _normalize_glyph(glyph: ImageArray) -> ImageArray:
    ys, xs = np.where(glyph > 0)
    if len(xs) == 0:
        return np.zeros((32, 24), dtype=np.uint8)
    cropped = glyph[min(ys) : max(ys) + 1, min(xs) : max(xs) + 1]
    return cv2.resize(cropped, (24, 32), interpolation=cv2.INTER_NEAREST)


def _overlap_score(first: ImageArray, second: ImageArray) -> float:
    first_mask = first > 0
    second_mask = second > 0
    union = np.count_nonzero(first_mask | second_mask)
    return float(np.count_nonzero(first_mask & second_mask) / union) if union else 0.0
