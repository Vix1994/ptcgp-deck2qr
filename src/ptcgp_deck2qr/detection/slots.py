"""Resolve raw region proposals into unique physical card slots."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

from .models import BoundingBox, CardSlot, RegionProposal, StyleName, make_slot_id


@dataclass(frozen=True, slots=True)
class SlotResolution:
    """Resolved slots plus structural errors from the resolver."""

    slots: tuple[CardSlot, ...]
    errors: tuple[str, ...] = ()
    dominant_width: float = 0.0
    dominant_height: float = 0.0


@dataclass(frozen=True, slots=True)
class _Geometry:
    width: float
    height: float

    @property
    def ratio(self) -> float:
        return self.width / max(self.height, 1.0)


@dataclass(slots=True)
class _Cluster:
    proposals: list[RegionProposal]
    center_x: float
    center_y: float

    def add(self, proposal: RegionProposal) -> None:
        self.proposals.append(proposal)
        count = len(self.proposals)
        self.center_x += (proposal.center_x - self.center_x) / count
        self.center_y += (proposal.center_y - self.center_y) / count


class SlotResolver:
    """Convert overlapping contour proposals into spatially unique card slots.

    The resolver is intentionally blind to card identity.  It uses the whole
    proposal set to estimate card geometry, clusters normalized centers, then
    assigns global row/column coordinates.  A nested contour therefore joins
    the same spatial cluster while two adjacent copies remain separate.
    """

    def __init__(self, style: StyleName, *, center_tolerance: float = 0.42) -> None:
        self.style = style
        self.center_tolerance = center_tolerance

    def resolve(self, proposals: Iterable[RegionProposal]) -> SlotResolution:
        ordered = tuple(sorted(proposals, key=_proposal_order))
        if not ordered:
            return SlotResolution(())
        geometry = _dominant_geometry(ordered)
        clusters = self._cluster(ordered, geometry)
        rows = self._rows(clusters, geometry)
        column_anchors = _global_column_anchors(rows, geometry)
        row_anchors = tuple(_row_anchor(row, geometry) for row in rows)
        assignments: list[dict[int, _Cluster]] = []
        errors: list[str] = []
        for row_clusters in rows:
            assignment, assignment_errors = _assign_columns(row_clusters, column_anchors, geometry)
            assignments.append(assignment)
            errors.extend(assignment_errors)
        inferred = _grid_inferred_positions(
            self.style,
            assignments,
            column_anchors,
            row_anchors,
            geometry,
        )
        slots: list[CardSlot] = []
        for row_index, assignment in enumerate(assignments):
            for column in range(len(column_anchors)):
                cluster = assignment.get(column)
                if cluster is None:
                    if (row_index, column) in inferred:
                        slots.append(
                            _make_inferred_slot(
                                index=len(slots) + 1,
                                row=row_index,
                                column=column,
                                center_x=column_anchors[column],
                                center_y=row_anchors[row_index],
                                geometry=geometry,
                                style=self.style,
                                support_rows=inferred[(row_index, column)],
                            )
                        )
                    continue
                representative = _choose_representative(cluster.proposals, geometry)
                members = tuple(sorted(cluster.proposals, key=_proposal_order))
                slots.append(
                    CardSlot(
                        index=len(slots) + 1,
                        bbox=representative.bbox,
                        detection_score=representative.detection_score,
                        crop_quality=representative.crop_quality,
                        style=self.style,
                        row=row_index,
                        column=column,
                        slot_id=make_slot_id(row_index, column),
                        proposals=members,
                        resolution_reason=(
                            f"center-cluster:{len(members)};"
                            f"representative:{representative.proposal_id};"
                            f"global-grid:{round(column_anchors[column])},{round(row_anchors[row_index])};"
                            f"dominant:{round(geometry.width)}x{round(geometry.height)}"
                        ),
                    )
                )
        ids = [slot.slot_id for slot in slots]
        if len(ids) != len(set(ids)):
            errors.append("duplicate-slot-conflict")
        return SlotResolution(
            tuple(slots),
            tuple(dict.fromkeys(errors)),
            dominant_width=geometry.width,
            dominant_height=geometry.height,
        )

    def _cluster(
        self, proposals: tuple[RegionProposal, ...], geometry: _Geometry
    ) -> list[_Cluster]:
        clusters: list[_Cluster] = []
        # Largest proposals seed clusters.  This makes a full-card contour the
        # geometric anchor without using card identity or a fixed coordinate.
        for proposal in sorted(proposals, key=_cluster_seed_order):
            nearest = min(
                clusters,
                key=lambda cluster: _normalized_distance(proposal, cluster, geometry),
                default=None,
            )
            if nearest is not None and _normalized_distance(proposal, nearest, geometry) <= (
                self.center_tolerance
            ):
                nearest.add(proposal)
            else:
                clusters.append(_Cluster([proposal], proposal.center_x, proposal.center_y))
        return clusters

    @staticmethod
    def _rows(clusters: list[_Cluster], geometry: _Geometry) -> list[list[_Cluster]]:
        rows: list[list[_Cluster]] = []
        for cluster in sorted(clusters, key=lambda item: (item.center_y, item.center_x)):
            nearest: list[_Cluster] | None = None
            nearest_distance = float("inf")
            for row in rows:
                row_center = sum(item.center_y for item in row) / len(row)
                distance = abs(cluster.center_y - row_center)
                if distance <= geometry.height * 0.45 and distance < nearest_distance:
                    nearest = row
                    nearest_distance = distance
            if nearest is None:
                rows.append([cluster])
            else:
                nearest.append(cluster)
        return rows


def _geometry_distance(proposal: RegionProposal, geometry: _Geometry) -> float:
    return abs(math.log(proposal.bbox.width / max(geometry.width, 1.0))) + abs(
        math.log(proposal.bbox.height / max(geometry.height, 1.0))
    )


def _cluster_anchor(cluster: _Cluster, geometry: _Geometry) -> RegionProposal:
    """Choose the proposal whose dimensions best represent the card core."""

    return min(
        cluster.proposals,
        key=lambda proposal: (_geometry_distance(proposal, geometry), -proposal.detection_score),
    )


def _row_anchor(row: list[_Cluster], geometry: _Geometry) -> float:
    return float(median([_cluster_anchor(cluster, geometry).center_y for cluster in row]))


def _global_column_anchors(rows: list[list[_Cluster]], geometry: _Geometry) -> tuple[float, ...]:
    """Cluster all row observations into one global set of column anchors."""

    values = sorted(_cluster_anchor(cluster, geometry).center_x for row in rows for cluster in row)
    if not values:
        return ()
    groups: list[list[float]] = []
    tolerance = max(1.0, geometry.width * 0.55)
    for value in values:
        if groups and value - float(median(groups[-1])) <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return tuple(float(median(group)) for group in groups)


def _assign_columns(
    row: list[_Cluster], anchors: tuple[float, ...], geometry: _Geometry
) -> tuple[dict[int, _Cluster], tuple[str, ...]]:
    assignment: dict[int, _Cluster] = {}
    errors: list[str] = []
    tolerance = max(1.0, geometry.width * 0.55)
    for cluster in row:
        anchor = _cluster_anchor(cluster, geometry)
        column = min(range(len(anchors)), key=lambda index: abs(anchor.center_x - anchors[index]))
        distance = abs(anchor.center_x - anchors[column])
        if distance > tolerance:
            errors.append("grid-anchor-conflict")
            continue
        if column in assignment:
            errors.append("duplicate-slot-conflict")
            continue
        assignment[column] = cluster
    return assignment, tuple(errors)


def _regular_spacing(values: tuple[float, ...], scale: float) -> bool:
    if len(values) < 2:
        return False
    gaps = [right - left for left, right in pairwise(values)]
    expected = float(median(gaps))
    return all(abs(gap - expected) <= max(scale * 0.45, expected * 0.35) for gap in gaps)


def _grid_inferred_positions(
    style: StyleName,
    assignments: list[dict[int, _Cluster]],
    column_anchors: tuple[float, ...],
    row_anchors: tuple[float, ...],
    geometry: _Geometry,
) -> dict[tuple[int, int], int]:
    """Return only strongly supported regular-grid gaps for badge layouts."""

    if style != "count-badge" or len(assignments) < 3 or len(column_anchors) < 3:
        return {}
    if not _regular_spacing(column_anchors, geometry.width) or not _regular_spacing(
        row_anchors, geometry.height
    ):
        return {}
    full_rows = sum(len(assignment) == len(column_anchors) for assignment in assignments)
    if full_rows < 2:
        return {}
    inferred: dict[tuple[int, int], int] = {}
    for row, assignment in enumerate(assignments):
        if len(assignment) < len(column_anchors) - 1:
            continue
        for column in range(len(column_anchors)):
            if column in assignment:
                continue
            # An edge omission is indistinguishable from a ragged final row;
            # only an interior geometric gap is strong enough to infer.  The
            # occupied columns on both sides also make the "gap" explicit.
            if column == 0 or column == len(column_anchors) - 1:
                continue
            if not any(existing < column for existing in assignment) or not any(
                existing > column for existing in assignment
            ):
                continue
            support_rows = sum(
                other_row != row and column in other_assignment
                for other_row, other_assignment in enumerate(assignments)
            )
            if support_rows >= 2:
                inferred[(row, column)] = support_rows
    return inferred


def _make_inferred_slot(
    *,
    index: int,
    row: int,
    column: int,
    center_x: float,
    center_y: float,
    geometry: _Geometry,
    style: StyleName,
    support_rows: int,
) -> CardSlot:
    width = max(1, round(geometry.width))
    height = max(1, round(geometry.height))
    bbox = BoundingBox(
        round(center_x - width / 2.0),
        round(center_y - height / 2.0),
        width,
        height,
    )
    return CardSlot(
        index=index,
        bbox=bbox,
        detection_score=0.0,
        crop_quality=1.0,
        style=style,
        row=row,
        column=column,
        slot_id=make_slot_id(row, column),
        proposals=(),
        resolution_reason=(
            f"grid-inferred;global-anchor:{round(center_x)},{round(center_y)};"
            f"support-rows:{support_rows};geometry:{width}x{height}"
        ),
    )


def _proposal_order(proposal: RegionProposal) -> tuple[int, int, int, int, str]:
    box = proposal.bbox
    return (box.y, box.x, box.width, box.height, proposal.proposal_id)


def _cluster_seed_order(proposal: RegionProposal) -> tuple[float, float, int, int, str]:
    box = proposal.bbox
    return (-float(box.area), -proposal.detection_score, box.y, box.x, proposal.proposal_id)


def _dominant_geometry(proposals: tuple[RegionProposal, ...]) -> _Geometry:
    return _Geometry(
        width=float(median([proposal.bbox.width for proposal in proposals])),
        height=float(median([proposal.bbox.height for proposal in proposals])),
    )


def _normalized_distance(proposal: RegionProposal, cluster: _Cluster, geometry: _Geometry) -> float:
    dx = (proposal.center_x - cluster.center_x) / max(geometry.width, 1.0)
    dy = (proposal.center_y - cluster.center_y) / max(geometry.height, 1.0)
    return math.hypot(dx, dy)


def _choose_representative(proposals: list[RegionProposal], geometry: _Geometry) -> RegionProposal:
    dominant_area = geometry.width * geometry.height

    def score(proposal: RegionProposal) -> float:
        box = proposal.bbox
        ratio_error = abs(math.log(max(box.width / max(box.height, 1), 0.01) / geometry.ratio))
        ratio_score = max(0.0, 1.0 - min(ratio_error, 1.0))
        # Keep a little headroom above one so a larger enclosing contour wins
        # a near-tied ratio comparison instead of the median-sized inner box.
        size_score = min(1.5, box.area / max(dominant_area, 1.0))
        detection_score = max(0.0, min(1.0, proposal.detection_score))
        border_score = max(0.0, min(1.0, proposal.border_score))
        # Size/fullness and border evidence make a complete outer contour win
        # over a nested inner contour with a nearly identical center.
        return 0.15 * ratio_score + 0.60 * size_score + 0.15 * detection_score + 0.10 * border_score

    return max(
        proposals,
        key=lambda proposal: (score(proposal), proposal.bbox.area, proposal.proposal_id),
    )
