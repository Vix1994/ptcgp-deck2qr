"""Load and validate an external ``ptcgp-database/dist`` directory."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date
from pathlib import Path
from typing import Any

from .errors import DatabaseSchemaError
from .identities import parse_image_identity
from .models import CardEntityKey, CardPrint, CardVisual, SourceManifest


@dataclass(frozen=True, slots=True)
class CardDatabase:
    """Validated normalized view over an external database release."""

    root: Path
    prints: tuple[CardPrint, ...]
    visuals: tuple[CardVisual, ...]
    release_order: dict[str, int]
    manifest: SourceManifest
    _prints_by_key: dict[tuple[str, int], CardPrint] = dataclass_field(
        init=False, repr=False, compare=False
    )
    _visuals_by_id: dict[str, CardVisual] = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_prints_by_key", {(x.set_code, x.number): x for x in self.prints})
        object.__setattr__(self, "_visuals_by_id", {x.visual_id: x for x in self.visuals})

    def resolve_print(self, set_code: str, number: int) -> CardPrint | None:
        """Resolve a Deck Text print key."""

        return self._prints_by_key.get((set_code, number))

    def visual(self, visual_id: str) -> CardVisual | None:
        """Resolve a normalized visual filename."""

        return self._visuals_by_id.get(visual_id)

    def all_visuals(self) -> tuple[CardVisual, ...]:
        return self.visuals


def load_database(root: str | Path) -> CardDatabase:
    """Load cards.json, sets.json, and cards-by-set artwork without copying them."""

    base = Path(root).expanduser().resolve()
    cards_path = base / "cards.json"
    sets_path = base / "sets.json"
    image_root = base / "images" / "cards-by-set"
    for required in (cards_path, sets_path, image_root):
        if not required.exists():
            raise DatabaseSchemaError(f"database path is missing {required}")
    cards = _read_json_array(cards_path)
    sets = _read_json_object(sets_path)
    set_info = _parse_sets(sets)
    prints: list[CardPrint] = []
    seen_keys: set[tuple[str, int]] = set()
    visual_entities: dict[str, CardEntityKey] = {}
    visual_prints: dict[str, list[str]] = defaultdict(list)
    for row_number, row in enumerate(cards, start=1):
        card = _parse_card_row(row, row_number)
        key = (card["set"], card["number"])
        if key in seen_keys:
            raise DatabaseSchemaError(f"duplicate print key: {key[0]}-{key[1]}")
        seen_keys.add(key)
        if card["set"] not in set_info:
            raise DatabaseSchemaError(f"card references unknown set: {card['set']}")
        image_path = image_root / card["set"] / f"{card['number']}.webp"
        if not image_path.is_file():
            raise DatabaseSchemaError(f"missing card image: {image_path}")
        entity = parse_image_identity(card["image"])
        previous = visual_entities.setdefault(card["image"], entity)
        if previous != entity:
            raise DatabaseSchemaError(f"visual maps to multiple entities: {card['image']}")
        info = set_info[card["set"]]
        print_id = f"{card['set']}-{card['number']:03d}"
        visual_prints[card["image"]].append(print_id)
        prints.append(
            CardPrint(
                set_code=card["set"],
                number=card["number"],
                name=card["name"],
                rarity=card["rarity"],
                image=card["image"],
                image_path=image_path,
                entity=entity,
                release_date=info["release_date"],
                release_order=info["release_order"],
                packs=card["packs"],
            )
        )
    print_by_id = {item.print_id: item for item in prints}
    visual_rows: list[CardVisual] = []
    for image, print_ids in sorted(visual_prints.items()):
        first_print = print_by_id[print_ids[0]]
        visual_rows.append(
            CardVisual(
                visual_id=image,
                image_path=first_print.image_path,
                entity=visual_entities[image],
                print_ids=tuple(sorted(print_ids)),
            )
        )
    visuals = tuple(visual_rows)
    manifest = SourceManifest(
        schema_version=1,
        cards_sha256=_sha256(cards_path),
        sets_sha256=_sha256(sets_path),
        card_count=len(prints),
        visual_count=len(visuals),
    )
    return CardDatabase(
        root=base,
        prints=tuple(
            sorted(prints, key=lambda item: (item.release_order, item.set_code, item.number))
        ),
        visuals=visuals,
        release_order={code: info["release_order"] for code, info in set_info.items()},
        manifest=manifest,
    )


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    value = _read_json(path)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise DatabaseSchemaError(f"expected JSON object array: {path}")
    return value


def _read_json_object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise DatabaseSchemaError(f"expected JSON object: {path}")
    return value


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatabaseSchemaError(f"cannot read JSON {path}: {exc}") from exc


def _parse_sets(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, value in raw.items():
        if not isinstance(value, list):
            raise DatabaseSchemaError(f"sets group {group!r} must be an array")
        rows.extend(value)
    parsed: list[tuple[str, date]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str):
            raise DatabaseSchemaError("set row is missing string code")
        code = row["code"]
        raw_date = row.get("releaseDate")
        if not isinstance(raw_date, str):
            raise DatabaseSchemaError(f"set {code} is missing releaseDate")
        try:
            parsed.append((code, date.fromisoformat(raw_date)))
        except ValueError as exc:
            raise DatabaseSchemaError(f"invalid releaseDate for set {code}: {raw_date}") from exc
    if len({code for code, _ in parsed}) != len(parsed):
        raise DatabaseSchemaError("duplicate set code")
    parsed.sort(key=lambda item: (item[1], item[0]))
    return {
        code: {"release_date": release_date, "release_order": index}
        for index, (code, release_date) in enumerate(parsed)
    }


def _parse_card_row(row: dict[str, Any], row_number: int) -> dict[str, Any]:
    required_strings = ("set", "name", "rarity", "image")
    for field_name in required_strings:
        if not isinstance(row.get(field_name), str) or not row[field_name].strip():
            raise DatabaseSchemaError(f"card row {row_number} has invalid {field_name}")
    number = row.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise DatabaseSchemaError(f"card row {row_number} has invalid number")
    packs = row.get("packs", [])
    if packs is None:
        packs = []
    if not isinstance(packs, list) or not all(isinstance(pack, str) for pack in packs):
        raise DatabaseSchemaError(f"card row {row_number} has invalid packs")
    return {
        "set": row["set"],
        "number": number,
        "name": row["name"].strip(),
        "rarity": row["rarity"].strip(),
        "image": row["image"].strip(),
        "packs": tuple(packs),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
