"""Screenshot-to-Deck Text orchestration for the current milestone."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .carddb import CardDatabase, CardPrint, IndexSourceMismatch, load_database
from .decktext import CardRef, Deck, DeckCard, DeckValidationError, validate_deck, write_deck_file
from .detection import (
    CardSlot,
    CountObservation,
    DetectionResult,
    RegionProposal,
    StyleName,
    detect_regions,
    extract_count,
)
from .matching import (
    FingerprintIndex,
    MatchResult,
    build_fingerprint_index,
    load_fingerprint_index,
    policy_for_style,
)

ImageArray = NDArray[Any]
_KNOWN_OUTPUTS = ("deck.txt", "deck.partial.txt", "recognition.json", "recognized.png")


@dataclass(frozen=True, slots=True)
class RecognitionCard:
    region: CardSlot
    match: MatchResult
    count: CountObservation

    @property
    def accepted(self) -> bool:
        # A lattice-inferred slot has no image evidence of its own.  It is
        # useful for geometry/debugging, but cannot silently contribute a
        # guessed card to a Deck Text result.
        return (
            not self.region.is_grid_inferred and self.match.accepted and self.count.count in (1, 2)
        )


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    accepted: bool
    output_dir: Path
    detection: DetectionResult
    cards: tuple[RecognitionCard, ...]
    errors: tuple[str, ...]
    deck: Deck | None = None


def recognize_image(
    image_path: str | Path,
    *,
    energy: str | tuple[str, ...],
    database_path: str | Path,
    output_dir: str | Path,
    style: StyleName = "auto",
    index_path: str | Path | None = None,
) -> RecognitionResult:
    """Recognize one screenshot and emit diagnostic artifacts.

    ``deck.txt`` is written only after every entity/count decision is accepted
    and the aggregate validates as a 20-card deck.  Diagnostics are written for
    both success and failure.
    """

    source = Path(image_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _clear_known_outputs(destination)
    energies = _parse_energy(energy)
    database = load_database(database_path)
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        detection = DetectionResult(style, 0.0, (), ("input-image-unreadable",))
        result = RecognitionResult(False, destination, detection, (), detection.errors)
        _write_diagnostics(result, source, database, energies, image=None)
        return result

    # Reading the input before constructing the full visual index avoids a
    # multi-second database/image pass for an invalid path or unreadable file.
    index = _get_index(index_path, database)

    detection = detect_regions(image, style)
    cards: list[RecognitionCard] = []
    badge_shape = _estimate_badge_card_shape(detection.slots)
    for region in detection.slots:
        crop = _matching_crop(image, region, badge_shape=badge_shape)
        artwork = detection.style == "quantity-label"
        match = _match(crop, index, style=detection.style, artwork=artwork)
        count = extract_count(image, region, style=detection.style)
        cards.append(RecognitionCard(region, match, count))
    result, deck = _make_result(source, destination, detection, tuple(cards), energies, database)
    if deck is not None and result.accepted:
        write_deck_file(deck, destination / "deck.txt", release_order=database.release_order)
    elif deck is not None:
        write_deck_file(
            deck, destination / "deck.partial.txt", release_order=database.release_order
        )
    _write_diagnostics(result, source, database, energies, image=image)
    return result


def _get_index(index_path: str | Path | None, database: CardDatabase) -> FingerprintIndex:
    if index_path is not None:
        path = Path(index_path)
        if not path.is_file():
            raise IndexSourceMismatch(
                f"fingerprint index does not exist: {path}; run build-index first"
            )
        return load_fingerprint_index(path, database)
    return build_fingerprint_index(database)


def _clear_known_outputs(destination: Path) -> None:
    """Remove only this tool's four replaceable output files."""

    for filename in _KNOWN_OUTPUTS:
        target = destination / filename
        if target.is_file() or target.is_symlink():
            target.unlink()


def _match(
    crop: ImageArray,
    index: FingerprintIndex,
    *,
    style: str,
    artwork: bool,
) -> MatchResult:
    from .matching import match_crop

    return match_crop(crop, index, artwork=artwork, policy=policy_for_style(style))


def _estimate_badge_card_shape(
    regions: tuple[CardSlot, ...],
) -> tuple[int, int] | None:
    """Estimate the unbadged card dimensions from a repeated badge grid.

    Badge contours may include the marker, but the repeated card height remains
    a useful robust estimate.  A standard portrait card is approximately 0.70
    as wide as it is tall; keeping this estimate separate from the detector's
    contour box avoids feeding red-marker/background pixels to the matcher.
    """

    if len(regions) < 3 or not all(region.style == "count-badge" for region in regions):
        return None
    proposals = [proposal for region in regions for proposal in region.proposals]
    card_like = [
        proposal
        for proposal in proposals
        if proposal.bbox.width / max(1, proposal.bbox.height) <= 0.72
    ]
    if not card_like:
        card_like = proposals
    if not card_like:
        return None
    ranked = sorted(card_like, key=lambda proposal: proposal.bbox.area)
    representative = ranked[int((len(ranked) - 1) * 0.80)]
    if representative.bbox.height < 20:
        return None
    return representative.bbox.width, representative.bbox.height


def _matching_crop(
    image: ImageArray,
    region: CardSlot,
    *,
    badge_shape: tuple[int, int] | None = None,
) -> ImageArray:
    """Trim a badge's external count marker before visual matching."""

    box = region.bbox
    if region.style == "count-badge" and (
        badge_shape is not None or box.width / max(1, box.height) > 0.74
    ):
        if badge_shape is None:
            core_height = max(1, int(box.height * 0.895))
            core_width = max(1, int(box.width * 0.84))
        else:
            core_width = min(box.width, badge_shape[0])
            core_height = min(box.height, badge_shape[1])
        return image[
            box.y : min(image.shape[0], box.y + core_height),
            box.x : min(image.shape[1], box.x + core_width),
        ]
    return image[box.y : box.bottom, box.x : box.right]


def _make_result(
    source: Path,
    destination: Path,
    detection: DetectionResult,
    cards: tuple[RecognitionCard, ...],
    energies: tuple[str, ...],
    database: CardDatabase,
) -> tuple[RecognitionResult, Deck | None]:
    errors = list(detection.errors)
    slot_ids = [card.region.slot_id for card in cards]
    if len(slot_ids) != len(set(slot_ids)):
        errors.append("duplicate-slot-conflict")
    if any(card.region.is_grid_inferred for card in cards):
        errors.append("slot-evidence-missing")
    if not cards:
        errors.append("card-region-not-found")
    if any(not card.match.accepted for card in cards):
        errors.append("match-ambiguous-entity")
    if any(card.count.count not in (1, 2) for card in cards):
        errors.append("count-ambiguous")
    deck = _build_deck(cards, energies, database, source.stem)
    if deck is None and cards:
        errors.append("card-aggregation-failed")
    if deck is not None:
        try:
            validate_deck(deck, resolver=database)
        except DeckValidationError as exc:
            errors.append(str(exc))
    accepted = not errors and deck is not None
    return RecognitionResult(
        accepted, destination, detection, cards, tuple(dict.fromkeys(errors)), deck
    ), deck


def _build_deck(
    cards: tuple[RecognitionCard, ...],
    energies: tuple[str, ...],
    database: CardDatabase,
    name: str,
) -> Deck | None:
    grouped: dict[tuple[str, int], DeckCard] = {}
    for card in cards:
        if not card.accepted or card.match.selected is None or card.count.count is None:
            continue
        selected = card.match.selected
        print = _canonical_print(selected.print_ids, database)
        if print is None:
            continue
        key = (print.set_code, print.number)
        section = "pokemon" if selected.entity_type == "pokemon" else "trainer"
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = DeckCard(
                ref=CardRef(print.set_code, print.number),
                name=print.name,
                count=card.count.count,
                section=section,  # type: ignore[arg-type]
            )
        else:
            grouped[key] = DeckCard(
                ref=existing.ref,
                name=existing.name,
                count=existing.count + card.count.count,
                section=existing.section,
            )
    if not grouped:
        return None
    pokemon = tuple(card for card in grouped.values() if card.section == "pokemon")
    trainer = tuple(card for card in grouped.values() if card.section == "trainer")
    return Deck(energies=energies, pokemon=pokemon, trainer=trainer, name=name)


def _canonical_print(print_ids: tuple[str, ...], database: CardDatabase) -> CardPrint | None:
    prints = []
    for print_id in print_ids:
        set_code, number = print_id.rsplit("-", 1)
        resolved = database.resolve_print(set_code, int(number))
        if resolved is not None:
            prints.append(resolved)
    return (
        min(prints, key=lambda item: (item.release_order, item.set_code, item.number))
        if prints
        else None
    )


def _parse_energy(value: str | tuple[str, ...]) -> tuple[str, ...]:
    raw = (
        value
        if isinstance(value, tuple)
        else tuple(part.strip().lower() for part in value.split(","))
    )
    if not raw or any(not item for item in raw):
        raise ValueError("energy must contain one to three comma-separated values")
    if len(raw) > 3 or len(set(raw)) != len(raw):
        raise ValueError("energy must contain one to three unique values")
    from .decktext import ALLOWED_ENERGIES

    unknown = set(raw) - ALLOWED_ENERGIES
    if unknown:
        raise ValueError(f"unknown energy: {', '.join(sorted(unknown))}")
    return raw


def _write_diagnostics(
    result: RecognitionResult,
    source: Path,
    database: CardDatabase,
    energies: tuple[str, ...],
    *,
    image: ImageArray | None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "input": str(source),
        "detected_style": result.detection.style,
        "style_confidence": result.detection.style_confidence,
        "style_evidence": list(result.detection.style_evidence),
        "database": database.manifest.to_dict(),
        "energy": list(energies),
        "proposals": [_proposal_json(proposal) for proposal in result.detection.proposals],
        "slots": [_slot_json(card.region) for card in result.cards],
        "match_policies": {
            card.match.policy.name: card.match.policy.to_dict() for card in result.cards
        },
        "cards": [_card_json(card, database) for card in result.cards],
        "validation": {
            "accepted": result.accepted,
            "errors": list(result.errors),
            "card_count": result.deck.total_count if result.deck is not None else 0,
        },
    }
    (result.output_dir / "recognition.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if image is not None:
        _write_annotated_image(
            image, result, result.output_dir / "recognized.png", database=database
        )
    else:
        placeholder = np.zeros((80, 360, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            "input image unreadable",
            (8, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 220),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(result.output_dir / "recognized.png"), placeholder)


def _card_json(card: RecognitionCard, database: CardDatabase) -> dict[str, Any]:
    selected = card.match.selected
    canonical = _canonical_print(selected.print_ids, database) if selected is not None else None
    selected_print = canonical.print_id if canonical is not None else None
    return {
        "slot": card.region.index,
        "slot_id": card.region.slot_id,
        "bbox": [
            card.region.bbox.x,
            card.region.bbox.y,
            card.region.bbox.width,
            card.region.bbox.height,
        ],
        "row": card.region.row,
        "column": card.region.column,
        "proposal_ids": [proposal.proposal_id for proposal in card.region.proposals],
        "proposal_count": len(card.region.proposals),
        "resolution_reason": card.region.resolution_reason,
        "detection_score": card.region.detection_score,
        "crop_quality": card.region.crop_quality,
        "count": card.count.count,
        "count_confidence": card.count.confidence,
        "count_method": card.count.method,
        "count_reason": card.count.reason,
        "decision": "accepted" if card.accepted else "rejected",
        "visual_id": selected.visual_id if selected is not None else None,
        "entity_type": selected.entity_type if selected is not None else None,
        "entity_id": selected.entity_number if selected is not None else None,
        "selected_print": selected_print,
        "print_candidates": list(selected.print_ids) if selected is not None else [],
        "visual_score": card.match.visual_score,
        "entity_margin": card.match.entity_margin,
        "match_policy": card.match.policy.to_dict(),
        "reason": card.match.reason,
        "top_candidates": [
            {
                "visual_id": candidate.visual_id,
                "score": candidate.score,
                "entity_type": candidate.entity_type,
                "entity_id": candidate.entity_number,
                "print_ids": list(candidate.print_ids),
            }
            for candidate in card.match.candidates
        ],
    }


def _proposal_json(proposal: RegionProposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id,
        "bbox": [
            proposal.bbox.x,
            proposal.bbox.y,
            proposal.bbox.width,
            proposal.bbox.height,
        ],
        "style": proposal.style,
        "detection_score": proposal.detection_score,
        "crop_quality": proposal.crop_quality,
        "border_score": proposal.border_score,
        "evidence": list(proposal.evidence),
    }


def _slot_json(slot: CardSlot) -> dict[str, Any]:
    return {
        "slot": slot.index,
        "slot_id": slot.slot_id,
        "bbox": [slot.bbox.x, slot.bbox.y, slot.bbox.width, slot.bbox.height],
        "row": slot.row,
        "column": slot.column,
        "detection_score": slot.detection_score,
        "crop_quality": slot.crop_quality,
        "proposal_ids": [proposal.proposal_id for proposal in slot.proposals],
        "proposal_count": len(slot.proposals),
        "resolution_reason": slot.resolution_reason,
    }


def _write_annotated_image(
    image: ImageArray,
    result: RecognitionResult,
    path: Path,
    *,
    database: CardDatabase | None = None,
) -> None:
    annotated = image.copy()
    for card in result.cards:
        box = card.region.bbox
        if card.accepted:
            color = (0, 180, 0)
        elif card.match.accepted:
            color = (0, 165, 255)
        else:
            color = (0, 0, 220)
        cv2.rectangle(annotated, (box.x, box.y), (box.right, box.bottom), color, 2)
        selected = card.match.selected
        label = f"{card.region.slot_id} p{len(card.region.proposals)}"
        if selected is not None:
            canonical = (
                _canonical_print(selected.print_ids, database) if database is not None else None
            )
            label += f" {canonical.print_id if canonical is not None else selected.visual_id}"
        metrics = (
            f" v{card.match.visual_score:.2f}"
            f" m{card.match.entity_margin:.3f}"
            f" c{card.count.confidence:.2f}"
        )
        font_scale = 0.27
        line_height = 12
        top = max(0, box.y + 2)
        right = min(annotated.shape[1] - 1, box.right - 1)
        bottom = min(annotated.shape[0] - 1, top + line_height * 2 + 2)
        cv2.rectangle(annotated, (box.x, top), (right, bottom), (20, 20, 20), -1)
        cv2.putText(
            annotated,
            label,
            (box.x + 2, top + line_height - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated,
            metrics.strip(),
            (box.x + 2, top + line_height * 2 - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            1,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), annotated)
