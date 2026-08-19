"""Immutable data contracts for screenshot proposals and resolved card slots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StyleName = Literal["auto", "separate-cards", "quantity-label", "count-text", "count-badge"]


@dataclass(frozen=True, slots=True, order=True)
class BoundingBox:
    """Pixel rectangle represented as ``x, y, width, height``."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0

    def clamp(self, width: int, height: int) -> BoundingBox:
        x = max(0, min(self.x, width - 1))
        y = max(0, min(self.y, height - 1))
        right = max(x + 1, min(self.right, width))
        bottom = max(y + 1, min(self.bottom, height))
        return BoundingBox(x, y, right - x, bottom - y)


@dataclass(frozen=True, slots=True)
class RegionProposal:
    """One raw contour-derived visual proposal.

    Proposals deliberately do not represent card identity or a final slot.  A
    single physical card may produce several nested or repeated proposals.
    ``border_score`` is a local evidence score used only by slot resolution.
    """

    proposal_id: str
    bbox: BoundingBox
    detection_score: float
    crop_quality: float
    style: StyleName
    border_score: float = 0.0
    evidence: tuple[str, ...] = ()

    @property
    def center_x(self) -> float:
        return self.bbox.center_x

    @property
    def center_y(self) -> float:
        return self.bbox.center_y


@dataclass(frozen=True, slots=True)
class CardSlot:
    """One unique physical card position consumed by matcher and counter."""

    index: int
    bbox: BoundingBox
    detection_score: float
    crop_quality: float
    style: StyleName
    row: int
    column: int
    slot_id: str = ""
    proposals: tuple[RegionProposal, ...] = ()
    resolution_reason: str = "explicit-slot"

    def __post_init__(self) -> None:
        if not self.slot_id:
            object.__setattr__(self, "slot_id", make_slot_id(self.row, self.column))

    @property
    def is_grid_inferred(self) -> bool:
        """Whether this slot was synthesized from a regular-grid gap."""

        return self.resolution_reason.startswith("grid-inferred")


def make_slot_id(row: int, column: int) -> str:
    """Build a stable position identity independent of card identity."""

    return f"r{row + 1:02d}c{column + 1:02d}"


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Detection output with raw proposals and resolved physical slots."""

    style: StyleName
    style_confidence: float
    regions: tuple[CardSlot, ...]
    errors: tuple[str, ...] = ()
    style_evidence: tuple[str, ...] = ()
    proposals: tuple[RegionProposal, ...] = ()

    @property
    def slots(self) -> tuple[CardSlot, ...]:
        """Preferred semantic name for resolved regions."""

        return self.regions


# Compatibility name for callers of the pre-slot API.  It is an alias rather
# than a second model: only CardSlot instances can flow past detection.
DetectedRegion = CardSlot
