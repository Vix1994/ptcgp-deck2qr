from __future__ import annotations

from pathlib import Path

from ptcgp_deck2qr.cli import main

from .helpers import make_database, make_screenshot


def test_cli_build_index_and_recognize(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    index = tmp_path / "index.json"
    assert main(["build-index", "--database-path", str(database), "--output", str(index)]) == 0
    image = tmp_path / "deck.png"
    make_screenshot(image)
    output = tmp_path / "output"
    assert (
        main(
            [
                "recognize",
                str(image),
                "--energy",
                "psychic,water",
                "--database-path",
                str(database),
                "--index-path",
                str(index),
                "--output-dir",
                str(output),
                "--style",
                "separate-cards",
            ]
        )
        == 0
    )
    assert (output / "deck.txt").exists()


def test_cli_rejects_missing_database() -> None:
    assert main(["build-index", "--database-path", "Z:\\missing", "--output", "x.json"]) == 5


def test_cli_reports_missing_explicit_index(tmp_path: Path) -> None:
    database = make_database(tmp_path, count=10)
    image = tmp_path / "deck.png"
    make_screenshot(image)
    code = main(
        [
            "recognize",
            str(image),
            "--energy",
            "fire",
            "--database-path",
            str(database),
            "--index-path",
            str(tmp_path / "missing-index.json"),
            "--output-dir",
            str(tmp_path / "output"),
        ]
    )
    assert code == 5
