"""Top-k fingerprint retrieval and entity-level fail-closed decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from numpy.typing import NDArray

from .fingerprints import Fingerprint, fingerprint_distance, fingerprint_image, hash_similarity
from .index import FingerprintIndex

ImageArray = NDArray[Any]


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

    def to_dict(self) -> dict[str, object]:
        """Return the exact policy values used for a match decision."""

        return {
            "name": self.name,
            "min_score": self.min_score,
            "min_entity_margin": self.min_entity_margin,
            "allow_strong_override": self.allow_strong_override,
            "strong_score": self.strong_score,
            "strong_margin": self.strong_margin,
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
    ordered = tuple(sorted(candidates, key=lambda item: item.score, reverse=True))
    if not ordered:
        return MatchResult(False, None, (), 0.0, 0.0, "no-candidates", active_policy)
    selected = ordered[0]
    distinct_scores = [
        item.score
        for item in ordered
        if item.entity_type != selected.entity_type or item.entity_number != selected.entity_number
    ]
    second = max(distinct_scores, default=0.0)
    margin = selected.score - second
    accepted = _accept_match(
        selected.score,
        margin,
        min_score=active_policy.min_score,
        min_entity_margin=active_policy.min_entity_margin,
        allow_strong_override=active_policy.allow_strong_override,
        strong_score=active_policy.strong_score,
        strong_margin=active_policy.strong_margin,
    )
    reason = (
        None
        if accepted
        else (
            "entity-ambiguous" if margin < active_policy.min_entity_margin else "visual-score-low"
        )
    )
    return MatchResult(
        accepted,
        selected,
        ordered[:top_k],
        selected.score,
        margin,
        reason,
        active_policy,
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
