from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptcgp_deck2qr.carddb import DatabaseSchemaError, load_database, parse_image_identity
from ptcgp_deck2qr.carddb.errors import IndexSourceMismatch
from ptcgp_deck2qr.carddb.loader import (
    _parse_card_row,
    _parse_sets,
    _read_json,
    _read_json_array,
    _read_json_object,
)
from ptcgp_deck2qr.carddb.models import CardPrintKey, SourceManifest
from ptcgp_deck2qr.matching import (
    build_fingerprint_index,
    load_fingerprint_index,
    save_fingerprint_index,
)

from .helpers import make_database


def test_database_loader_normalizes_print_visual_entity(tmp_path: Path) -> None:
    dist = make_database(tmp_path, count=4)
    database = load_database(dist)
    assert len(database.prints) == 4
    assert len(database.visuals) == 4
    assert database.prints[0].print_id == "A1-001"
    assert database.prints[0].entity.code == "PK:1"
    assert database.prints[0].key == CardPrintKey("A1", 1)
    assert database.resolve_print("A1", 2) is not None
    assert database.resolve_print("A9", 1) is None
    assert database.visual(database.visuals[0].visual_id) is not None
    assert len(database.all_visuals()) == 4
    assert SourceManifest(1, "a", "b", 1, 1, source_version="v").to_dict()["source_version"] == "v"


def test_identity_parser_and_invalid_database_rows(tmp_path: Path) -> None:
    assert parse_image_identity("cPK_10_000010_00_X.webp").code == "PK:10"
    assert parse_image_identity("cTR_10_000170_00_X.webp").code == "TR:170"
    with pytest.raises(DatabaseSchemaError):
        parse_image_identity("unknown.webp")
    with pytest.raises(DatabaseSchemaError):
        parse_image_identity("cPK_10_000000_00_X.webp")

    dist = make_database(tmp_path, count=2)
    cards_path = dist / "cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    cards[1]["set"] = "UNKNOWN"
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    with pytest.raises(DatabaseSchemaError, match="unknown set"):
        load_database(dist)


def test_index_round_trip_and_source_mismatch(tmp_path: Path) -> None:
    dist = make_database(tmp_path, count=3)
    database = load_database(dist)
    index = build_fingerprint_index(database)
    path = tmp_path / "index.json"
    save_fingerprint_index(index, path)
    loaded = load_fingerprint_index(path, database)
    assert len(loaded.entries) == 3
    cards_path = dist / "cards.json"
    cards_path.write_text(cards_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed = load_database(dist)
    with pytest.raises(Exception, match="mismatch"):
        load_fingerprint_index(path, changed)


def test_index_rejects_malformed_payloads(tmp_path: Path) -> None:
    dist = make_database(tmp_path, count=2)
    database = load_database(dist)
    path = tmp_path / "bad.json"
    for payload, message in (
        ([], "root"),
        ({}, "manifest"),
        ({"manifest": {}}, "schema_version"),
        ({"manifest": database.manifest.to_dict()}, "unsupported fingerprint index schema"),
    ):
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(IndexSourceMismatch, match=message):
            load_fingerprint_index(path, database)


def test_index_rejects_tampered_algorithm_and_identity_mappings(tmp_path: Path) -> None:
    dist = make_database(tmp_path, count=3)
    database = load_database(dist)
    index = build_fingerprint_index(database)
    path = tmp_path / "index.json"
    save_fingerprint_index(index, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for field, message in (
        ("algorithm_version", "top-level fingerprint algorithm"),
        ("artwork_crop_policy", "top-level artwork crop policy"),
    ):
        tampered = json.loads(json.dumps(payload))
        tampered[field] = "tampered"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(IndexSourceMismatch, match=message):
            load_fingerprint_index(path, database)
    for field, value, message in (
        ("entity_type", "trainer", "entity mapping"),
        ("print_ids", ["A1-999"], "print mapping"),
        ("visual_id", "unknown-visual", "visual IDs"),
    ):
        tampered = json.loads(json.dumps(payload))
        tampered["entries"][0][field] = value
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(IndexSourceMismatch, match=message):
            load_fingerprint_index(path, database)


def test_database_schema_helpers_reject_bad_rows_and_files(tmp_path: Path) -> None:
    with pytest.raises(DatabaseSchemaError, match="missing"):
        load_database(tmp_path / "missing")
    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(DatabaseSchemaError, match="array"):
        _read_json_array(raw)
    raw.write_text("[]", encoding="utf-8")
    with pytest.raises(DatabaseSchemaError, match="object"):
        _read_json_object(raw)
    raw.write_text("not json", encoding="utf-8")
    with pytest.raises(DatabaseSchemaError, match="cannot read"):
        _read_json(raw)

    with pytest.raises(DatabaseSchemaError, match="group"):
        _parse_sets({"A": {}})
    with pytest.raises(DatabaseSchemaError, match="string code"):
        _parse_sets({"A": [{}]})
    with pytest.raises(DatabaseSchemaError, match="releaseDate"):
        _parse_sets({"A": [{"code": "A1"}]})
    with pytest.raises(DatabaseSchemaError, match="invalid releaseDate"):
        _parse_sets({"A": [{"code": "A1", "releaseDate": "bad"}]})
    duplicate_sets = {
        "A": [
            {"code": "A1", "releaseDate": "2024-01-01"},
            {"code": "A1", "releaseDate": "2024-01-02"},
        ]
    }
    with pytest.raises(DatabaseSchemaError, match="duplicate set"):
        _parse_sets(duplicate_sets)

    valid = {"set": "A1", "number": 1, "name": "A", "rarity": "C", "image": "cPK_10_000001_00_X"}
    for field in ("set", "name", "rarity", "image"):
        bad = dict(valid)
        bad[field] = ""
        with pytest.raises(DatabaseSchemaError, match=field):
            _parse_card_row(bad, 1)
    for number in (True, 0, "1"):
        bad = dict(valid)
        bad["number"] = number
        with pytest.raises(DatabaseSchemaError, match="number"):
            _parse_card_row(bad, 1)
    none_packs = dict(valid, packs=None)
    assert _parse_card_row(none_packs, 1)["packs"] == ()
    with pytest.raises(DatabaseSchemaError, match="packs"):
        _parse_card_row(dict(valid, packs=[1]), 1)


def test_database_row_validation_duplicate_and_missing_image(tmp_path: Path) -> None:
    dist = make_database(tmp_path, count=2)
    cards_path = dist / "cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    cards.append(cards[0])
    cards_path.write_text(json.dumps(cards), encoding="utf-8")
    with pytest.raises(DatabaseSchemaError, match="duplicate print"):
        load_database(dist)

    dist = make_database(tmp_path / "other", count=2)
    (dist / "images" / "cards-by-set" / "A1" / "2.webp").unlink()
    with pytest.raises(DatabaseSchemaError, match="missing card image"):
        load_database(dist)
