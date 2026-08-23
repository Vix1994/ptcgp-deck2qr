"""Top-k fingerprint retrieval and entity-level fail-closed decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from numpy.typing import NDArray

from .alignment import (
    LocalAlignmentEvidence,
    add_orb_evidence,
    align_candidate,
    build_artwork_query,
    multiview_hash_similarity,
)
from .fingerprints import Fingerprint, fingerprint_distance, fingerprint_image, hash_similarity
from .index import FingerprintIndex, IndexEntry

ImageArray = NDArray[Any]
_LOCAL_CANDIDATE_COUNT = 12
_ORB_CANDIDATE_COUNT = 4


@dataclass(frozen=True, slots=True)
class MatchPolicy:
    """Named acceptance rules for one screenshot presentation style.

    ``score`` is a ranking score produced by the classical visual matcher, not
    a probability.  Keeping the thresholds in a named policy makes the
    fail-closed decision auditable in diagnostics and prevents a permissive
    full-card fallback from accidentally being used for partial card crops.
    """

    name: str
    min_score: float
    min_entity_margin: float
    allow_strong_override: bool = False
    strong_score: float = 0.94
    strong_margin: float = 0.025
    min_visible_patches: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return the exact policy values used for a match decision."""

        return {
            "name": self.name,
            "min_score": self.min_score,
            "min_entity_margin": self.min_entity_margin,
            "allow_strong_override": self.allow_strong_override,
            "strong_score": self.strong_score,
            "strong_margin": self.strong_margin,
            "min_visible_patches": self.min_visible_patches,
        }


FULL_CARD_POLICY = MatchPolicy(
    name="full-card-v1",
    min_score=0.68,
    min_entity_margin=0.035,
    allow_strong_override=True,
)

# Quantity labels expose only a partial artwork crop.  The stricter policy is
# intentional: partial crops have less evidence than a full card and must not
# turn a plausible near-neighbour into an accepted entity.
QUANTITY_ARTWORK_POLICY = MatchPolicy(
    name="quantity-artwork-strict-v1",
    min_score=0.80,
    min_entity_margin=0.06,
)

# Badge screenshots include a small external count marker and can contain
# resampling/background pixels around the card.  They use a separate strict
# policy rather than inheriting the full-card strong-match exception.
COUNT_BADGE_POLICY = MatchPolicy(
    name="count-badge-strict-v1",
    min_score=0.84,
    min_entity_margin=0.06,
)

# Portrait screenshots now identify the entity from the illustration first.
# Unlike the quantity layout, the source crop still contains a full card, so
# this policy describes which feature family is primary rather than a distinct
# detector layout.
PORTRAIT_ARTWORK_POLICY = MatchPolicy(
    name="portrait-artwork-aligned-v2",
    min_score=0.70,
    min_entity_margin=0.04,
    min_visible_patches=6,
)

# A recovered slot has no contour of its own, so grid geometry is allowed to
# locate the crop but never to identify the card.  Only the illustration ROI
# may supply that missing evidence, under thresholds stricter than the normal
# full-card path and without the strong-match margin override.
GRID_RECOVERED_ARTWORK_POLICY = MatchPolicy(
    name="grid-recovered-artwork-aligned-strict-v2",
    min_score=0.74,
    min_entity_margin=0.05,
    min_visible_patches=6,
)


def policy_for_style(style: str) -> MatchPolicy:
    """Select an explicit matcher policy for a detected screenshot style."""

    if style == "quantity-label":
        return QUANTITY_ARTWORK_POLICY
    if style == "count-badge":
        return COUNT_BADGE_POLICY
    # Separate cards and count-text retain the established full-card baseline.
    return FULL_CARD_POLICY


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    visual_id: str
    print_ids: tuple[str, ...]
    entity_type: str
    entity_number: int
    score: float
    coarse_score: float = 0.0
    aligned_patch_score: float = 0.0
    visible_patch_count: int = 0
    orb_inliers: int = 0
    orb_inlier_ratio: float = 0.0


@dataclass(frozen=True, slots=True)
class MatchResult:
    accepted: bool
    selected: MatchCandidate | None
    candidates: tuple[MatchCandidate, ...]
    visual_score: float
    entity_margin: float
    reason: str | None = None
    policy: MatchPolicy = FULL_CARD_POLICY


def match_crop(
    crop: ImageArray,
    index: FingerprintIndex,
    *,
    artwork: bool = False,
    top_k: int = 10,
    min_score: float = 0.68,
    min_entity_margin: float = 0.035,
    policy: MatchPolicy | None = None,
) -> MatchResult:
    """Retrieve top-k visual candidates and reject weak entity decisions."""

    active_policy = policy or _policy_from_legacy_thresholds(min_score, min_entity_margin)
    query = fingerprint_image(crop)
    return _match_fingerprint(
        query,
        index,
        artwork=artwork,
        top_k=top_k,
        policy=active_policy,
    )


def match_card_face(
    crop: ImageArray,
    index: FingerprintIndex,
    *,
    top_k: int = 10,
    policy: MatchPolicy | None = None,
) -> MatchResult:
    """Match a portrait card through shifted recall and local alignment.

    The input is only an approximate slot. Nine bounded artwork views make
    coarse retrieval tolerant of translation, then the top candidates are
    aligned at several scales and scored from their six strongest 3x3 patches.
    ORB/RANSAC inliers add independent local-feature evidence when available.
    """

    active_policy = policy or PORTRAIT_ARTWORK_POLICY
    query = build_artwork_query(crop)
    pool_size = max(top_k, _LOCAL_CANDIDATE_COUNT)
    rough = sorted(
        index.entries,
        key=lambda entry: multiview_hash_similarity(query, entry.fingerprint),
        reverse=True,
    )[:pool_size]
    local_candidates: list[tuple[IndexEntry, float, LocalAlignmentEvidence]] = []
    for entry in rough:
        coarse_score = max(
            _score(view, entry.fingerprint, artwork=True) for view in query.fingerprints
        )
        local = align_candidate(query, entry)
        local_candidates.append((entry, coarse_score, local))
    local_candidates.sort(
        key=lambda item: 0.24 * item[1] + 0.76 * item[2].aligned_score,
        reverse=True,
    )
    verified = {
        entry.visual_id: add_orb_evidence(query, entry, local)
        for entry, _, local in local_candidates[:_ORB_CANDIDATE_COUNT]
    }
    candidates: list[MatchCandidate] = []
    for entry, coarse_score, local in local_candidates:
        evidence = verified.get(entry.visual_id, local)
        score = 0.24 * coarse_score + 0.76 * evidence.aligned_score
        candidates.append(
            MatchCandidate(
                visual_id=entry.visual_id,
                print_ids=entry.print_ids,
                entity_type=entry.entity_type,
                entity_number=entry.entity_number,
                score=max(0.0, min(1.0, score)),
                coarse_score=coarse_score,
                aligned_patch_score=evidence.patch_score,
                visible_patch_count=evidence.visible_patches,
                orb_inliers=evidence.orb_inliers,
                orb_inlier_ratio=evidence.orb_inlier_ratio,
            )
        )
    return _result_from_candidates(
        tuple(candidates),
        top_k=top_k,
        policy=active_policy,
    )


def _match_fingerprint(
    query: Fingerprint,
    index: FingerprintIndex,
    *,
    artwork: bool,
    top_k: int,
    policy: MatchPolicy,
) -> MatchResult:
    """Match one precomputed query fingerprint with an explicit feature family."""

    rough = sorted(
        index.entries,
        key=lambda entry: 1.0 - hash_similarity(query, entry.fingerprint, artwork=artwork),
    )[: max(top_k, 2)]
    candidates = tuple(
        MatchCandidate(
            visual_id=entry.visual_id,
            print_ids=entry.print_ids,
            entity_type=entry.entity_type,
            entity_number=entry.entity_number,
            # Hash-only retrieval is deliberately followed by a separate
            # color/correlation rerank.  The two stages must not collapse into
            # the same distance calculation.
            score=_score(query, entry.fingerprint, artwork=artwork),
        )
        for entry in rough
    )
    return _result_from_candidates(candidates, top_k=top_k, policy=policy)


def _result_from_candidates(
    candidates: tuple[MatchCandidate, ...],
    *,
    top_k: int,
    policy: MatchPolicy,
) -> MatchResult:
    """Apply entity-level margin and visible-evidence rules to ranked candidates."""

    ordered = tuple(sorted(candidates, key=lambda item: item.score, reverse=True))
    if not ordered:
        return MatchResult(False, None, (), 0.0, 0.0, "no-candidates", policy)
    selected = ordered[0]
    distinct_scores = [
        item.score
        for item in ordered
        if item.entity_type != selected.entity_type or item.entity_number != selected.entity_number
    ]
    second = max(distinct_scores, default=0.0)
    margin = selected.score - second
    accepted = (
        _accept_match(
            selected.score,
            margin,
            min_score=policy.min_score,
            min_entity_margin=policy.min_entity_margin,
            allow_strong_override=policy.allow_strong_override,
            strong_score=policy.strong_score,
            strong_margin=policy.strong_margin,
        )
        and selected.visible_patch_count >= policy.min_visible_patches
    )
    reason = (
        None
        if accepted
        else (
            "visible-artwork-insufficient"
            if selected.visible_patch_count < policy.min_visible_patches
            else "entity-ambiguous"
            if margin < policy.min_entity_margin
            else "visual-score-low"
        )
    )
    return MatchResult(
        accepted,
        selected,
        ordered[:top_k],
        selected.score,
        margin,
        reason,
        policy,
    )


def _policy_from_legacy_thresholds(min_score: float, min_entity_margin: float) -> MatchPolicy:
    """Preserve the old threshold-only API while making it auditable."""

    if (
        min_score == FULL_CARD_POLICY.min_score
        and min_entity_margin == FULL_CARD_POLICY.min_entity_margin
    ):
        return FULL_CARD_POLICY
    return MatchPolicy(
        name="custom-thresholds-v1",
        min_score=min_score,
        min_entity_margin=min_entity_margin,
    )


def _score(query: Fingerprint, reference: Fingerprint, *, artwork: bool) -> float:
    distance = fingerprint_distance(query, reference, artwork=artwork)
    # Keep the score explicit as a ranking score, not a probability.
    return max(0.0, min(1.0, 1.0 - distance))


def _accept_match(
    score: float,
    margin: float,
    *,
    min_score: float,
    min_entity_margin: float,
    allow_strong_override: bool | None = None,
    strong_score: float = 0.94,
    strong_margin: float = 0.025,
) -> bool:
    """Apply an evidence-backed dual threshold for baseline visual matches.

    A very strong visual match can be accepted with a slightly smaller margin
    than the conservative default, while callers that pass explicit strict
    thresholds retain exact ``score AND margin`` semantics.
    """

    if score < min_score:
        return False
    if margin >= min_entity_margin:
        return True
    if allow_strong_override is None:
        allow_strong_override = (
            min_score == FULL_CARD_POLICY.min_score
            and min_entity_margin == FULL_CARD_POLICY.min_entity_margin
        )
    return allow_strong_override and score >= strong_score and margin >= strong_margin
