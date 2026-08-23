"""Rebuildable classical visual fingerprint index and matcher."""

from .index import (
    FINGERPRINT_ALGORITHM_VERSION,
    FingerprintIndex,
    build_fingerprint_index,
    load_fingerprint_index,
    save_fingerprint_index,
)
from .matcher import (
    COUNT_BADGE_POLICY,
    FULL_CARD_POLICY,
    GRID_RECOVERED_ARTWORK_POLICY,
    PORTRAIT_ARTWORK_POLICY,
    QUANTITY_ARTWORK_POLICY,
    MatchCandidate,
    MatchPolicy,
    MatchResult,
    match_card_face,
    match_crop,
    policy_for_style,
)

__all__ = [
    "COUNT_BADGE_POLICY",
    "FINGERPRINT_ALGORITHM_VERSION",
    "FULL_CARD_POLICY",
    "GRID_RECOVERED_ARTWORK_POLICY",
    "PORTRAIT_ARTWORK_POLICY",
    "QUANTITY_ARTWORK_POLICY",
    "FingerprintIndex",
    "MatchCandidate",
    "MatchPolicy",
    "MatchResult",
    "build_fingerprint_index",
    "load_fingerprint_index",
    "match_card_face",
    "match_crop",
    "policy_for_style",
    "save_fingerprint_index",
]
