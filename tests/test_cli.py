from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from ptcgp_deck2qr.cli import build_parser, main
from ptcgp_deck2qr.gui import GuiConfig

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


def test_cli_launches_gui_with_runtime_paths(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    captured_config: list[GuiConfig] = []
    browser_flags: list[bool] = []

    def fake_run_gui(config: GuiConfig, *, open_browser: bool) -> None:
        captured_config.append(config)
        browser_flags.append(open_browser)

    monkeypatch.setattr("ptcgp_deck2qr.gui.run_gui", fake_run_gui)
    database = tmp_path / "database"
    output = tmp_path / "result"
    assert (
        main(
            [
                "gui",
                "--database-path",
                str(database),
                "--output-dir",
                str(output),
                "--port",
                "9001",
                "--no-open",
            ]
        )
        == 0
    )
    config = captured_config[0]
    assert config.database_path == database
    assert config.output_dir == output
    assert config.port == 9001
    assert browser_flags == [False]


def test_gui_uses_existing_documented_index_by_default(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    index = tmp_path / "data" / "index" / "fingerprint.json"
    index.parent.mkdir(parents=True)
    index.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    args = build_parser().parse_args(["gui", "--database-path", str(tmp_path / "database")])

    assert args.index_path == Path("data/index/fingerprint.json")
