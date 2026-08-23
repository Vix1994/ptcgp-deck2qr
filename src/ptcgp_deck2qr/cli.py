"""Command-line entry points for the recognition MVP."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .carddb import DatabaseError, load_database
from .matching import build_fingerprint_index, save_fingerprint_index
from .pipeline import recognize_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ptcgp-deck2qr")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    recognize = commands.add_parser("recognize", help="recognize a deck screenshot")
    recognize.add_argument("image", type=Path)
    recognize.add_argument("--energy", required=True, help="comma-separated energy names")
    recognize.add_argument(
        "--database-path",
        type=Path,
        default=_database_from_environment(),
        help="external ptcgp-database/dist path (or PTCGP_DATABASE_PATH)",
    )
    recognize.add_argument("--output-dir", "--output", type=Path, default=Path("output"))
    recognize.add_argument(
        "--style",
        choices=("auto", "separate-cards", "quantity-label", "count-text", "count-badge"),
        default="auto",
    )
    recognize.add_argument("--index-path", type=Path)

    build = commands.add_parser("build-index", help="build a rebuildable visual index")
    build.add_argument(
        "--database-path",
        type=Path,
        default=_database_from_environment(),
        help="external ptcgp-database/dist path (or PTCGP_DATABASE_PATH)",
    )
    build.add_argument("--output", type=Path, default=Path("data/index/fingerprint.json"))

    gui = commands.add_parser("gui", help="launch the local browser GUI")
    gui.add_argument(
        "--database-path",
        type=Path,
        default=_database_from_environment(),
        help="external ptcgp-database/dist path (or PTCGP_DATABASE_PATH)",
    )
    gui.add_argument("--output-dir", "--output", type=Path, default=Path("output"))
    gui.add_argument("--index-path", type=Path, default=_existing_default_index())
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-open", action="store_true", help="do not open a browser automatically")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build-index":
            if args.database_path is None:
                parser.error("--database-path or PTCGP_DATABASE_PATH is required")
            database = load_database(args.database_path)
            index = build_fingerprint_index(database)
            save_fingerprint_index(index, args.output)
            print(f"built {len(index.entries)} visual fingerprints at {args.output}")
            return 0
        if args.command == "gui":
            if args.database_path is None:
                parser.error("--database-path or PTCGP_DATABASE_PATH is required")
            from .gui import GuiConfig, run_gui

            run_gui(
                GuiConfig(
                    database_path=args.database_path,
                    output_dir=args.output_dir,
                    index_path=args.index_path,
                    host=args.host,
                    port=args.port,
                ),
                open_browser=not args.no_open,
            )
            return 0
        if args.database_path is None:
            parser.error("--database-path or PTCGP_DATABASE_PATH is required")
        result = recognize_image(
            args.image,
            energy=args.energy,
            database_path=args.database_path,
            output_dir=args.output_dir,
            style=args.style,
            index_path=args.index_path,
        )
        if result.accepted:
            print(f"recognized deck: {args.output_dir / 'deck.txt'}")
            return 0
        print(f"recognition rejected; see {args.output_dir / 'recognition.json'}")
        return 3 if any("match" in error or "count" in error for error in result.errors) else 4
    except (DatabaseError, OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 5 if isinstance(exc, DatabaseError) else 1


def _database_from_environment() -> Path | None:
    value = os.environ.get("PTCGP_DATABASE_PATH")
    return Path(value) if value else None


def _existing_default_index() -> Path | None:
    """Use the documented local index automatically when it already exists."""

    path = Path("data/index/fingerprint.json")
    return path if path.is_file() else None


if __name__ == "__main__":
    raise SystemExit(main())
