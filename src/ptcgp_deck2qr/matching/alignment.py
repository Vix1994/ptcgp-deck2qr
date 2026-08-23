"""Crop-tolerant local artwork alignment and occlusion-aware evidence."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .fingerprints import Fingerprint, artwork_crop, fingerprint_image, hash_similarity
from .index import IndexEntry

ImageArray = NDArray[Any]
_VIEW_SHIFTS = (-0.04, 0.0, 0.04)
_ALIGNMENT_SCALES = (0.90, 0.95, 1.0, 1.05, 1.10)
_PATCH_GRID = 3
_ROBUST_PATCH_COUNT = 6
_VISIBLE_PATCH_SCORE = 0.56
_PATCH_ALIGNMENT_COUNT = 2


@dataclass(frozen=True, slots=True)
class ArtworkQuery:
    """Reusable evidence extracted once from one approximate portrait slot."""

    card: ImageArray
    search_bgr: ImageArray
    search_gray: ImageArray
    artwork_shape: tuple[int, int]
    fingerprints: tuple[Fingerprint, ...]
    keypoints: tuple[tuple[float, float], ...]
    descriptors: ImageArray | None


@dataclass(frozen=True, slots=True)
class LocalAlignmentEvidence:
    """Independent visual measurements for one database candidate."""

    aligned_score: float
    patch_score: float
    template_score: float
    visible_patches: int
    orb_inliers: int
    orb_inlier_ratio: float


@dataclass(frozen=True, slots=True)
class _ReferenceArtwork:
    bgr: ImageArray
    gray: ImageArray


@dataclass(frozen=True, slots=True)
class _TemplateAlignment:
    template_score: float
    location: tuple[int, int]
    resized: ImageArray


def build_artwork_query(card: ImageArray) -> ArtworkQuery:
    """Build shifted coarse views and local features from an approximate card crop."""

    if card.size == 0:
        raise ValueError("cannot align an empty card crop")
    bgr = card if card.ndim == 3 else cv2.cvtColor(card, cv2.COLOR_GRAY2BGR)
    search = _artwork_search_window(bgr)
    search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    keypoints, descriptors = _orb_features(search_gray)
    artwork = artwork_crop(bgr)
    return ArtworkQuery(
        card=bgr,
        search_bgr=search,
        search_gray=search_gray,
        artwork_shape=(int(artwork.shape[0]), int(artwork.shape[1])),
        fingerprints=tuple(fingerprint_image(view) for view in _shifted_artwork_views(bgr)),
        keypoints=keypoints,
        descriptors=descriptors,
    )


def multiview_hash_similarity(query: ArtworkQuery, reference: Fingerprint) -> float:
    """Return the best artwork hash similarity over bounded shifted views."""

    return max(hash_similarity(view, reference, artwork=True) for view in query.fingerprints)


def align_candidate(query: ArtworkQuery, entry: IndexEntry) -> LocalAlignmentEvidence:
    """Align one reference artwork and score only its strongest visible patches."""

    if entry.image_path is None:
        return LocalAlignmentEvidence(0.0, 0.0, 0.0, 0, 0, 0.0)
    reference = _load_reference_artwork(str(entry.image_path))
    if reference is None:
        return LocalAlignmentEvidence(0.0, 0.0, 0.0, 0, 0, 0.0)

    alignments: list[_TemplateAlignment] = []
    artwork_height, artwork_width = query.artwork_shape
    for scale in _ALIGNMENT_SCALES:
        width = max(12, round(artwork_width * scale))
        height = max(12, round(artwork_height * scale))
        if width > query.search_gray.shape[1] or height > query.search_gray.shape[0]:
            continue
        resized = cv2.resize(reference.bgr, (width, height), interpolation=cv2.INTER_AREA)
        resized_gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        response = cv2.matchTemplate(
            query.search_gray,
            resized_gray,
            cv2.TM_CCOEFF_NORMED,
        )
        _, raw_template, _, location = cv2.minMaxLoc(response)
        template_score = max(0.0, min(1.0, (float(raw_template) + 1.0) / 2.0))
        alignments.append(
            _TemplateAlignment(
                template_score,
                (int(location[0]), int(location[1])),
                resized,
            )
        )

    best_template = 0.0
    best_patch_score = 0.0
    best_visible = 0
    for alignment in sorted(
        alignments,
        key=lambda item: item.template_score,
        reverse=True,
    )[:_PATCH_ALIGNMENT_COUNT]:
        height, width = alignment.resized.shape[:2]
        left, top = alignment.location
        observed = query.search_bgr[top : top + height, left : left + width]
        patch_score, visible = _robust_patch_score(observed, alignment.resized)
        template_score = alignment.template_score
        aligned = 0.22 * template_score + 0.78 * patch_score
        current = 0.22 * best_template + 0.78 * best_patch_score
        if (aligned, visible, template_score) > (current, best_visible, best_template):
            best_template = template_score
            best_patch_score = patch_score
            best_visible = visible

    local_score = 0.22 * best_template + 0.78 * best_patch_score
    return LocalAlignmentEvidence(
        aligned_score=max(0.0, min(1.0, local_score)),
        patch_score=best_patch_score,
        template_score=best_template,
        visible_patches=best_visible,
        orb_inliers=0,
        orb_inlier_ratio=0.0,
    )


def add_orb_evidence(
    query: ArtworkQuery,
    entry: IndexEntry,
    evidence: LocalAlignmentEvidence,
) -> LocalAlignmentEvidence:
    """Add feature verification after cheaper local alignment has reranked candidates."""

    if entry.image_path is None:
        return evidence
    reference = _load_reference_artwork(str(entry.image_path))
    if reference is None:
        return evidence
    reference_keypoints, reference_descriptors = _load_reference_orb(str(entry.image_path))
    orb_inliers, orb_ratio = _orb_evidence(
        query,
        reference_keypoints,
        reference_descriptors,
    )
    orb_score = _orb_score(orb_inliers, orb_ratio)
    # Feature verification may corroborate a locally aligned candidate, but a
    # texture-poor illustration must not be penalized merely because ORB found
    # few usable corners. Keeping the update non-decreasing also guarantees
    # that the locally leading candidates remain the feature-verified set.
    aligned_score = (
        0.90 * evidence.aligned_score + 0.10 * max(evidence.aligned_score, orb_score)
        if orb_inliers >= 4
        else evidence.aligned_score
    )
    return LocalAlignmentEvidence(
        aligned_score=max(0.0, min(1.0, aligned_score)),
        patch_score=evidence.patch_score,
        template_score=evidence.template_score,
        visible_patches=evidence.visible_patches,
        orb_inliers=orb_inliers,
        orb_inlier_ratio=orb_ratio,
    )


def _artwork_search_window(card: ImageArray) -> ImageArray:
    height, width = card.shape[:2]
    top = max(0, round(height * 0.01))
    bottom = min(height, max(top + 1, round(height * 0.68)))
    left = max(0, round(width * 0.01))
    right = min(width, max(left + 1, round(width * 0.99)))
    return card[top:bottom, left:right]


def _shifted_artwork_views(card: ImageArray) -> tuple[ImageArray, ...]:
    return tuple(
        artwork_crop(
            card,
            horizontal_shift=horizontal,
            vertical_shift=vertical,
        )
        for vertical in _VIEW_SHIFTS
        for horizontal in _VIEW_SHIFTS
    )


def _robust_patch_score(observed: ImageArray, reference: ImageArray) -> tuple[float, int]:
    if observed.shape[:2] != reference.shape[:2] or observed.size == 0:
        return 0.0, 0
    height, width = observed.shape[:2]
    xs = np.linspace(0, width, _PATCH_GRID + 1, dtype=np.int32)
    ys = np.linspace(0, height, _PATCH_GRID + 1, dtype=np.int32)
    scores: list[float] = []
    for row in range(_PATCH_GRID):
        for column in range(_PATCH_GRID):
            observed_tile = observed[ys[row] : ys[row + 1], xs[column] : xs[column + 1]]
            reference_tile = reference[ys[row] : ys[row + 1], xs[column] : xs[column + 1]]
            scores.append(_tile_similarity(observed_tile, reference_tile))
    ordered = sorted(scores, reverse=True)
    strongest = ordered[:_ROBUST_PATCH_COUNT]
    visible = sum(score >= _VISIBLE_PATCH_SCORE for score in scores)
    return (float(np.mean(strongest)) if strongest else 0.0), visible


def _tile_similarity(first: ImageArray, second: ImageArray) -> float:
    if first.size == 0 or second.size == 0:
        return 0.0
    first_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    second_gray = cv2.cvtColor(second, cv2.COLOR_BGR2GRAY)
    intensity = _normalized_similarity(first_gray, second_gray)

    first_edges = cv2.Sobel(first_gray, cv2.CV_32F, 1, 1, ksize=3)
    second_edges = cv2.Sobel(second_gray, cv2.CV_32F, 1, 1, ksize=3)
    edges = _normalized_similarity(first_edges, second_edges)

    first_hist = cv2.calcHist([first], [0, 1], None, [8, 8], [0, 256, 0, 256])
    second_hist = cv2.calcHist([second], [0, 1], None, [8, 8], [0, 256, 0, 256])
    cv2.normalize(first_hist, first_hist)
    cv2.normalize(second_hist, second_hist)
    color = max(
        0.0,
        min(1.0, (float(cv2.compareHist(first_hist, second_hist, cv2.HISTCMP_CORREL)) + 1.0) / 2.0),
    )
    return 0.55 * intensity + 0.25 * edges + 0.20 * color


def _normalized_similarity(first: ImageArray, second: ImageArray) -> float:
    first_values = first.astype(np.float32).reshape(-1)
    second_values = second.astype(np.float32).reshape(-1)
    first_values -= float(first_values.mean())
    second_values -= float(second_values.mean())
    denominator = float(np.linalg.norm(first_values) * np.linalg.norm(second_values))
    if denominator < 1e-6:
        difference = float(np.mean(np.abs(first.astype(np.float32) - second.astype(np.float32))))
        return max(0.0, 1.0 - difference / 255.0)
    correlation = float(np.dot(first_values, second_values) / denominator)
    return max(0.0, min(1.0, (correlation + 1.0) / 2.0))


def _orb_evidence(
    query: ArtworkQuery,
    reference_keypoints: tuple[tuple[float, float], ...],
    reference_descriptors: ImageArray | None,
) -> tuple[int, float]:
    if query.descriptors is None or reference_descriptors is None:
        return 0, 0.0
    if len(query.descriptors) < 2 or len(reference_descriptors) < 2:
        return 0, 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(reference_descriptors, query.descriptors, k=2)
    good = [
        pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.78 * pair[1].distance
    ]
    if len(good) < 4:
        return 0, 0.0
    source = np.asarray(
        [reference_keypoints[item.queryIdx] for item in good], dtype=np.float32
    ).reshape(-1, 1, 2)
    destination = np.asarray(
        [query.keypoints[item.trainIdx] for item in good], dtype=np.float32
    ).reshape(-1, 1, 2)
    try:
        _, mask = cv2.findHomography(source, destination, cv2.RANSAC, 3.0)
    except cv2.error:
        return 0, 0.0
    if mask is None:
        return 0, 0.0
    inliers = int(mask.ravel().sum())
    return inliers, inliers / len(good)


def _orb_score(inliers: int, ratio: float) -> float:
    return 0.60 * min(1.0, inliers / 12.0) + 0.40 * max(0.0, min(1.0, ratio))


def _orb_features(gray: ImageArray) -> tuple[tuple[tuple[float, float], ...], ImageArray | None]:
    orb_factory: Any = cv2.ORB_create  # type: ignore[attr-defined]
    detector = orb_factory(
        nfeatures=256,
        scaleFactor=1.2,
        nlevels=4,
        edgeThreshold=7,
        patchSize=15,
        fastThreshold=8,
    )
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    points = tuple((float(item.pt[0]), float(item.pt[1])) for item in keypoints)
    return points, descriptors


@lru_cache(maxsize=1024)
def _load_reference_artwork(path_text: str) -> _ReferenceArtwork | None:
    image = cv2.imread(str(Path(path_text)), cv2.IMREAD_COLOR)
    if image is None:
        return None
    artwork = artwork_crop(image)
    if artwork.size == 0:
        return None
    gray = cv2.cvtColor(artwork, cv2.COLOR_BGR2GRAY)
    return _ReferenceArtwork(artwork, gray)


@lru_cache(maxsize=1024)
def _load_reference_orb(
    path_text: str,
) -> tuple[tuple[tuple[float, float], ...], ImageArray | None]:
    reference = _load_reference_artwork(path_text)
    if reference is None:
        return (), None
    return _orb_features(reference.gray)
