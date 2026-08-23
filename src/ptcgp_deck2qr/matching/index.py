"""Build, serialize, and validate a rebuildable fingerprint index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2

from ptcgp_deck2qr.carddb import CardDatabase, IndexSourceMismatch

from .fingerprints import ARTWORK_CROP_POLICY_VERSION, Fingerprint, fingerprint_image

FINGERPRINT_ALGORITHM_VERSION = "hash-color-correlation-artwork-v3"
INDEX_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class IndexEntry:
    visual_id: str
    fingerprint: Fingerprint
    entity_type: str
    entity_number: int
    print_ids: tuple[str, ...]
    image_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "visual_id": self.visual_id,
            "fingerprint": self.fingerprint.to_dict(),
            "entity_type": self.entity_type,
            "entity_number": self.entity_number,
            "print_ids": list(self.print_ids),
        }


@dataclass(frozen=True, slots=True)
class FingerprintIndex:
    manifest: dict[str, object]
    entries: tuple[IndexEntry, ...]
    algorithm_version: str = FINGERPRINT_ALGORITHM_VERSION
    artwork_crop_policy: str = ARTWORK_CROP_POLICY_VERSION


def build_fingerprint_index(database: CardDatabase) -> FingerprintIndex:
    """Build an index from unique visual assets in the external database."""

    entries: list[IndexEntry] = []
    for visual in database.visuals:
        image = cv2.imread(str(visual.image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"cannot read card image: {visual.image_path}")
        fingerprint = fingerprint_image(image)
        entries.append(
            IndexEntry(
                visual_id=visual.visual_id,
                fingerprint=fingerprint,
                entity_type=visual.entity.entity_type,
                entity_number=visual.entity.number,
                print_ids=visual.print_ids,
                image_path=visual.image_path,
            )
        )
    manifest = dict(database.manifest.to_dict())
    manifest.update(
        {
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "fingerprint_algorithm": FINGERPRINT_ALGORITHM_VERSION,
            "artwork_crop_policy": ARTWORK_CROP_POLICY_VERSION,
            "rejected_row_count": 0,
        }
    )
    return FingerprintIndex(manifest=manifest, entries=tuple(entries))


def save_fingerprint_index(index: FingerprintIndex, path: str | Path) -> None:
    """Serialize an index as deterministic JSON."""

    payload = {
        "manifest": index.manifest,
        "algorithm_version": index.algorithm_version,
        "artwork_crop_policy": index.artwork_crop_policy,
        "entries": [entry.to_dict() for entry in index.entries],
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_fingerprint_index(path: str | Path, database: CardDatabase) -> FingerprintIndex:
    """Load an index only when it matches the current database source hashes."""

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexSourceMismatch(f"cannot read fingerprint index {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise IndexSourceMismatch("fingerprint index root must be an object")
    manifest = raw.get("manifest")
    if not isinstance(manifest, dict):
        raise IndexSourceMismatch("fingerprint index is missing manifest")
    expected = database.manifest.to_dict()
    for field in ("schema_version", "cards_sha256", "sets_sha256", "card_count", "visual_count"):
        if manifest.get(field) != expected[field]:
            raise IndexSourceMismatch(f"index source mismatch in {field}; rebuild the index")
    if manifest.get("index_schema_version") != INDEX_SCHEMA_VERSION:
        raise IndexSourceMismatch("unsupported fingerprint index schema; rebuild the index")
    if manifest.get("fingerprint_algorithm") != FINGERPRINT_ALGORITHM_VERSION:
        raise IndexSourceMismatch("fingerprint algorithm mismatch; rebuild the index")
    if manifest.get("artwork_crop_policy") != ARTWORK_CROP_POLICY_VERSION:
        raise IndexSourceMismatch("artwork crop policy mismatch; rebuild the index")
    if raw.get("algorithm_version") != FINGERPRINT_ALGORITHM_VERSION:
        raise IndexSourceMismatch("top-level fingerprint algorithm mismatch; rebuild the index")
    if raw.get("artwork_crop_policy") != ARTWORK_CROP_POLICY_VERSION:
        raise IndexSourceMismatch("top-level artwork crop policy mismatch; rebuild the index")
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list):
        raise IndexSourceMismatch("fingerprint index entries must be an array")
    database_visuals = {visual.visual_id: visual for visual in database.visuals}
    entries: list[IndexEntry] = []
    try:
        for item in entries_raw:
            if not isinstance(item, dict):
                raise ValueError("entry is not an object")
            fingerprint_raw = item.get("fingerprint")
            print_ids_raw = item.get("print_ids")
            entity_type = item.get("entity_type")
            entity_number = item.get("entity_number")
            visual_id = item.get("visual_id")
            if (
                not isinstance(fingerprint_raw, dict)
                or not isinstance(print_ids_raw, list)
                or not all(isinstance(value, str) for value in print_ids_raw)
                or not isinstance(entity_type, str)
                or not isinstance(entity_number, int)
                or not isinstance(visual_id, str)
            ):
                raise ValueError("entry has invalid fields")
            entries.append(
                IndexEntry(
                    visual_id=visual_id,
                    fingerprint=Fingerprint.from_dict(fingerprint_raw),
                    entity_type=entity_type,
                    entity_number=entity_number,
                    print_ids=tuple(print_ids_raw),
                    image_path=(
                        database_visuals[visual_id].image_path
                        if visual_id in database_visuals
                        else None
                    ),
                )
            )
    except (TypeError, ValueError) as exc:
        raise IndexSourceMismatch(f"invalid fingerprint index entry: {exc}") from exc
    entry_ids = [entry.visual_id for entry in entries]
    if len(entry_ids) != len(set(entry_ids)):
        raise IndexSourceMismatch("index contains duplicate visual IDs; rebuild the index")
    if set(entry_ids) != set(database_visuals):
        raise IndexSourceMismatch("index visual IDs do not match database; rebuild the index")
    for entry in entries:
        visual = database_visuals[entry.visual_id]
        if (
            entry.entity_type != visual.entity.entity_type
            or entry.entity_number != visual.entity.number
        ):
            raise IndexSourceMismatch(
                f"index entity mapping mismatch for {entry.visual_id}; rebuild the index"
            )
        if entry.print_ids != visual.print_ids:
            raise IndexSourceMismatch(
                f"index print mapping mismatch for {entry.visual_id}; rebuild the index"
            )
    return FingerprintIndex(
        manifest=manifest,
        entries=tuple(entries),
        algorithm_version=FINGERPRINT_ALGORITHM_VERSION,
        artwork_crop_policy=ARTWORK_CROP_POLICY_VERSION,
    )
