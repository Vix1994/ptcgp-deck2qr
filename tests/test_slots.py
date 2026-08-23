from __future__ import annotations

from ptcgp_deck2qr.detection import BoundingBox, RegionProposal, SlotResolver


def _proposal(
    proposal_id: str, box: BoundingBox, *, style: str = "separate-cards"
) -> RegionProposal:
    return RegionProposal(
        proposal_id=proposal_id,
        bbox=box,
        detection_score=0.9,
        crop_quality=0.95,
        style=style,  # type: ignore[arg-type]
        border_score=0.9,
        evidence=("synthetic-contour",),
    )


def test_nested_realistic_outer_and_inner_boxes_resolve_to_one_full_slot() -> None:
    outer = _proposal("outer", BoundingBox(846, 883, 189, 264))
    inner = _proposal("inner", BoundingBox(855, 905, 172, 218))

    result = SlotResolver("separate-cards").resolve((outer, inner))

    assert len(result.slots) == 1
    slot = result.slots[0]
    assert slot.bbox == outer.bbox
    assert slot.slot_id == "r01c01"
    assert {proposal.proposal_id for proposal in slot.proposals} == {"outer", "inner"}
    assert "representative:outer" in slot.resolution_reason


def test_three_nested_proposals_remain_one_physical_slot() -> None:
    proposals = (
        _proposal("outer", BoundingBox(100, 100, 120, 170)),
        _proposal("middle", BoundingBox(104, 108, 112, 160)),
        _proposal("inner", BoundingBox(108, 114, 104, 150)),
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    assert len(result.slots) == 1
    assert result.slots[0].bbox == proposals[0].bbox
    assert len(result.slots[0].proposals) == 3


def test_adjacent_touching_cards_are_not_spatially_merged() -> None:
    proposals = (
        _proposal("left", BoundingBox(0, 0, 120, 170)),
        _proposal("right", BoundingBox(121, 0, 120, 170)),
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    assert len(result.slots) == 2
    assert [slot.slot_id for slot in result.slots] == ["r01c01", "r01c02"]


def test_same_visual_identity_at_different_positions_is_kept_twice() -> None:
    # The resolver sees no Card ID at all; two spatial positions must remain
    # independent even when the proposal evidence is otherwise identical.
    proposals = (
        _proposal("same-card-a", BoundingBox(20, 20, 120, 170)),
        _proposal("same-card-b", BoundingBox(220, 20, 120, 170)),
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    assert len(result.slots) == 2
    assert {slot.slot_id for slot in result.slots} == {"r01c01", "r01c02"}


def test_badge_grid_uses_global_columns_and_infers_one_supported_gap() -> None:
    proposals = tuple(
        _proposal(
            f"r{row}c{column}",
            BoundingBox(column * 140, row * 200, 120, 170),
            style="count-badge",
        )
        for row in range(3)
        for column in range(5)
        if not (row == 0 and column == 2)
    )

    result = SlotResolver("count-badge").resolve(proposals)

    assert len(result.slots) == 15
    inferred = [slot for slot in result.slots if slot.is_grid_inferred]
    assert len(inferred) == 1
    assert inferred[0].slot_id == "r01c03"
    assert inferred[0].bbox == BoundingBox(280, 0, 120, 170)
    assert inferred[0].proposals == ()
    assert inferred[0].resolution_reason.startswith("grid-inferred")
    # The cards after the gap retain their global columns rather than shifting
    # left to fill the row-local list.
    row_one = [slot for slot in result.slots if slot.row == 0]
    assert [slot.slot_id for slot in row_one] == [
        "r01c01",
        "r01c02",
        "r01c03",
        "r01c04",
        "r01c05",
    ]


def test_separate_card_grid_proposes_one_supported_missing_contour() -> None:
    proposals = tuple(
        _proposal(
            f"r{row}c{column}",
            BoundingBox(column * 140, row * 200, 120, 170),
        )
        for row in range(4)
        for column in range(5)
        if not (row == 1 and column == 2)
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    assert len(result.slots) == 20
    recovered = [slot for slot in result.slots if slot.is_grid_inferred]
    assert len(recovered) == 1
    assert recovered[0].slot_id == "r02c03"
    assert recovered[0].bbox == BoundingBox(280, 200, 120, 170)
    assert recovered[0].proposals == ()


def test_separate_card_grid_proposes_a_supported_edge_gap() -> None:
    proposals = tuple(
        _proposal(
            f"r{row}c{column}",
            BoundingBox(column * 140, row * 200, 120, 170),
        )
        for row in range(4)
        for column in range(5)
        if not (row == 0 and column == 4)
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    recovered = [slot for slot in result.slots if slot.is_grid_inferred]
    assert len(result.slots) == 20
    assert len(recovered) == 1
    assert recovered[0].slot_id == "r01c05"
    assert recovered[0].bbox == BoundingBox(560, 0, 120, 170)


def test_regular_grid_normalizes_one_distorted_direct_contour() -> None:
    proposals = tuple(
        _proposal(
            f"r{row}c{column}",
            BoundingBox(
                column * 140,
                row * 200 + (7 if (row, column) == (1, 0) else 0),
                116 if (row, column) == (1, 0) else 120,
                163 if (row, column) == (1, 0) else 170,
            ),
        )
        for row in range(4)
        for column in range(5)
    )

    result = SlotResolver("separate-cards").resolve(proposals)

    target = next(slot for slot in result.slots if slot.slot_id == "r02c01")
    assert target.bbox == BoundingBox(0, 200, 120, 170)
    assert target.proposals[0].bbox == BoundingBox(0, 207, 116, 163)
    assert "crop:grid-normalized" in target.resolution_reason


def test_ragged_non_badge_layouts_do_not_infer_missing_slots() -> None:
    for style, width, height in (
        ("quantity-label", 200, 120),
        ("count-text", 120, 170),
    ):
        proposals = tuple(
            _proposal(
                f"{style}-{row}-{column}",
                BoundingBox(column * (width + 20), row * (height + 30), width, height),
                style=style,
            )
            for row, columns in enumerate((5, 4, 3))
            for column in range(columns)
        )
        result = SlotResolver(style).resolve(proposals)  # type: ignore[arg-type]

        assert len(result.slots) == 12
        assert not any(slot.is_grid_inferred for slot in result.slots)

    # A badge-style ragged edge is proposed geometrically, but it is not yet a
    # card. The pipeline must discard it unless artwork independently matches.
    proposals = tuple(
        _proposal(
            f"badge-{row}-{column}",
            BoundingBox(column * 140, row * 200, 120, 170),
            style="count-badge",
        )
        for row, columns in enumerate((5, 5, 4))
        for column in range(columns)
    )
    result = SlotResolver("count-badge").resolve(proposals)
    inferred = [slot for slot in result.slots if slot.is_grid_inferred]
    assert len(result.slots) == 15
    assert len(inferred) == 1
    assert inferred[0].slot_id == "r03c05"
