"""Layout-agnostic rectangle detection for clean deck screenshots."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .models import (
    BoundingBox,
    CardSlot,
    DetectedRegion,
    DetectionResult,
    RegionProposal,
    StyleName,
)
from .slots import SlotResolver

ImageArray = NDArray[Any]

__all__ = [
    "BoundingBox",
    "CardSlot",
    "DetectedRegion",
    "DetectionResult",
    "RegionProposal",
    "StyleName",
    "detect_regions",
]


def detect_regions(image: ImageArray, style: StyleName = "auto") -> DetectionResult:
    """Find card-like rectangles using edges, morphology, and grid consistency.

    This baseline intentionally only accepts upright, mostly rectangular screenshot
    cards.  It does not hallucinate a regular grid when no visual boundary exists.
    """

    if image.ndim not in (2, 3) or image.shape[0] < 20 or image.shape[1] < 20:
        return DetectionResult("auto", 0.0, (), ("invalid-image",))
    height, width = image.shape[:2]
    proposals = _find_candidates(image, style)
    if not proposals:
        return DetectionResult(style, 0.0, (), ("card-region-not-found",))
    inferred, style_evidence = _infer_style(image, proposals, style, width, height)
    filtered = tuple(
        replace(
            proposal,
            style=inferred,
            crop_quality=round(
                _crop_quality(proposal.bbox.width, proposal.bbox.height, inferred), 4
            ),
        )
        for proposal in proposals
        if _fits_style(proposal, inferred)
    )
    resolution = SlotResolver(inferred).resolve(filtered)
    slots = resolution.slots
    confidence = min(1.0, max(0.0, 0.55 + 0.1 * min(len(slots), 5)))
    errors = list(resolution.errors)
    if not slots:
        errors.append("card-region-not-found")
    return DetectionResult(
        inferred,
        confidence,
        slots,
        tuple(dict.fromkeys(errors)),
        style_evidence,
        filtered,
    )


def _find_candidates(image: ImageArray, style: StyleName) -> list[RegionProposal]:
    height, width = image.shape[:2]
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 35, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(width * height)
    candidates: list[RegionProposal] = []
    requested_landscape = style == "quantity-label"
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = box_width * box_height
        ratio = box_width / max(1, box_height)
        area_ratio = area / image_area
        if area_ratio < 0.01 or area_ratio > 0.55:
            continue
        if requested_landscape:
            if not 1.15 <= ratio <= 2.2 or box_width < width * 0.13:
                continue
        elif style == "auto":
            if not 0.45 <= ratio <= 2.2:
                continue
            if ratio > 1.05 and box_width < width * 0.15:
                continue
        elif (
            style in ("separate-cards", "count-text", "count-badge", "auto")
            and not 0.58 <= ratio <= 0.82
        ):
            continue
        # The closer a candidate is to a card ratio and a useful screenshot scale,
        # the more likely it is to be the outer card contour rather than text.
        target = 1.55 if requested_landscape else 0.72
        ratio_score = max(0.0, 1.0 - abs(ratio - target) / target)
        scale_score = min(1.0, area_ratio / 0.02)
        detection_score = 0.5 * ratio_score + 0.5 * scale_score
        expected_perimeter = max(1.0, 2.0 * (box_width + box_height))
        border_score = max(0.0, min(1.0, cv2.arcLength(contour, True) / expected_perimeter))
        candidates.append(
            RegionProposal(
                proposal_id=f"p{len(candidates) + 1:04d}",
                bbox=BoundingBox(x, y, box_width, box_height),
                detection_score=round(detection_score, 4),
                crop_quality=round(_crop_quality(box_width, box_height, style), 4),
                style=style,
                border_score=round(border_score, 4),
                evidence=(
                    "contour",
                    f"aspect-ratio:{ratio_score:.3f}",
                    f"scale:{scale_score:.3f}",
                    f"border:{border_score:.3f}",
                ),
            )
        )
    return candidates


def _infer_style(
    image: ImageArray,
    candidates: list[RegionProposal],
    requested: StyleName,
    width: int,
    height: int,
) -> tuple[StyleName, tuple[str, ...]]:
    if requested != "auto":
        return requested, (f"explicit:{requested}",)
    # Style evidence should not be multiplied by nested contour duplicates,
    # but the original proposals remain intact for the final resolver. Build
    # spatial observations separately by orientation so unrelated text/border
    # contours cannot dominate the card geometry median.
    landscape_proposals = [
        proposal
        for proposal in candidates
        if proposal.bbox.width / max(1, proposal.bbox.height) > 1.05
    ]
    landscape_slots = SlotResolver("auto").resolve(landscape_proposals).slots
    if len(landscape_slots) > max(2, len(candidates) // 3):
        return "quantity-label", (f"landscape-slots:{len(landscape_slots)}",)

    vertical_proposals = [
        proposal
        for proposal in candidates
        if 0.58 <= proposal.bbox.width / max(1, proposal.bbox.height) <= 0.82
    ]
    vertical = SlotResolver("auto").resolve(vertical_proposals).slots
    if not vertical:
        return "separate-cards", ("no-vertical-candidates",)

    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    red_mask = (
        ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 55)
    )
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    badge_scores = [_outside_badge_score(red_mask, item.bbox, width, height) for item in vertical]
    badge_hits = sum(score >= 0.10 for score in badge_scores)
    if badge_hits >= max(3, int(np.ceil(len(vertical) * 0.25))):
        return "count-badge", (f"badge-red-evidence:{badge_hits}/{len(vertical)}",)

    # Count labels are in the gap below a card.  A real gap is important: it
    # prevents the dense lower card border in tightly packed instance grids
    # from being mistaken for a text label.
    text_scores = [
        _below_label_score(
            edges,
            item.bbox,
            [candidate.bbox for candidate in vertical],
            width,
            height,
        )
        for item in vertical
    ]
    text_hits = sum(score >= 0.05 for score in text_scores)
    if text_hits >= max(3, int(np.ceil(len(vertical) * 0.35))):
        return "count-text", (f"count-text-edge-evidence:{text_hits}/{len(vertical)}",)
    return "separate-cards", ("no-count-marker-evidence",)


def _outside_badge_score(red_mask: ImageArray, box: BoundingBox, width: int, height: int) -> float:
    x, y, box_width, box_height = box.x, box.y, box.width, box.height
    left = max(0, x + int(box_width * 0.70))
    top = max(0, y + int(box_height * 0.78))
    right = min(width, x + int(box_width * 1.25))
    bottom = min(height, y + int(box_height * 1.20))
    if right <= left or bottom <= top:
        return 0.0
    return float(np.mean(red_mask[top:bottom, left:right]))


def _below_label_score(
    edges: ImageArray,
    box: BoundingBox,
    all_boxes: list[BoundingBox],
    width: int,
    height: int,
) -> float:
    x, y, box_width, box_height = box.x, box.y, box.width, box.height
    left = max(0, x + int(box_width * 0.25))
    right = min(width, x + int(box_width * 1.00))
    top = min(height, y + box_height)
    next_tops = [
        other_box.y
        for other_box in all_boxes
        if other_box.y > top
        and min(x + box_width, other_box.right) - max(x, other_box.x) > box_width * 0.25
    ]
    gap_limit = min(next_tops, default=height) - top
    if gap_limit <= int(box_height * 0.08):
        return 0.0
    bottom = min(height, top + int(box_height * 0.22), top + gap_limit)
    if right <= left or bottom <= top:
        return 0.0
    band = edges[top:bottom, left:right]
    if band.size == 0:
        return 0.0
    return float(np.mean(band > 0))


def _fits_style(candidate: RegionProposal, style: StyleName) -> bool:
    width, height = candidate.bbox.width, candidate.bbox.height
    ratio = width / max(1, height)
    if style == "quantity-label":
        return 1.15 <= ratio <= 2.2
    return 0.58 <= ratio <= 0.82


def _crop_quality(width: int, height: int, style: StyleName) -> float:
    target = 1.55 if style == "quantity-label" else 0.72
    ratio = width / max(1, height)
    return max(0.0, min(1.0, 1.0 - abs(ratio - target) / target))
