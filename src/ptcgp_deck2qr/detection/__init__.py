"""Classical screenshot region and quantity detection."""

from .counts import CountObservation, extract_count
from .models import CardSlot, RegionProposal
from .regions import BoundingBox, DetectedRegion, DetectionResult, StyleName, detect_regions
from .slots import SlotResolution, SlotResolver

__all__ = [
    "BoundingBox",
    "CardSlot",
    "CountObservation",
    "DetectedRegion",
    "DetectionResult",
    "RegionProposal",
    "SlotResolution",
    "SlotResolver",
    "StyleName",
    "detect_regions",
    "extract_count",
]
