# ptcgp-deck2qr

Convert a Pokémon TCG Pocket deck screenshot into a canonical, human-editable deck text file.

> Status: pre-alpha local screenshot-to-Deck-Text-and-QR MVP.

## Optional Game8 userscript

The independent [Game8 Tampermonkey adapter](userscript/README.md) adds a `生成 QR`
button to structured Game8 deck-list sections. It validates the page's 20-card list and
generates a deck-share QR locally in the browser.

[Install the current userscript directly from GitHub Raw](https://raw.githubusercontent.com/Vix1994/ptcgp-deck2qr/main/userscript/release/game8-ptcgp-deck-qr.user.js).
After this one-time installation, Tampermonkey checks a lightweight metadata file and
updates the script automatically when its version increases. The installed loader keeps
the versioned core and compact card map as separate integrity-checked resources, so a
normal code update does not replace the unchanged map.

This adapter is separate from the screenshot-recognition milestone below; it does not
add QR encoding to, or depend on, the recognition pipeline.

## Current scope

The first milestone is deliberately narrow:

```text
deck screenshot + explicit energy selection
  -> card/entity/count recognition
  -> validated Deck model
  -> canonical deck.txt
  -> local Deck Code + QR
```

QR encoding remains an independent downstream stage. This keeps image recognition testable without
coupling it to a reverse-engineered game payload.

## Recognition CLI

```text
output/
├── deck.txt
├── recognition.json
└── recognized.png
```

Build a rebuildable local fingerprint index from an external database release:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe build-index `
  --database-path H:\CodexCode\ptcgp-database\dist `
  --output data\index\fingerprint.json
```

Recognize a screenshot with explicit energy input:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe recognize deck.png `
  --energy lightning `
  --database-path H:\CodexCode\ptcgp-database\dist `
  --index-path data\index\fingerprint.json `
  --output-dir output
```

Low-confidence entity or count decisions fail closed: diagnostics are still
written, but a successful `deck.txt` is not emitted. Use `--style` to override
automatic layout classification when a screenshot is ambiguous.

## Local GUI

Launch the optional React interface around the same recognition pipeline:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe gui `
  --database-path H:\CodexCode\ptcgp-database\dist `
  --index-path data\index\fingerprint.json `
  --output-dir output
```

The browser opens on `127.0.0.1`. Select, drag, or paste a clipboard image with `Ctrl+V`; then choose
energy and run recognition. After a validated 20-card result, the GUI automatically generates a QR
and offers PNG download and Deck Code copy. A structurally reliable 18-19 card result can instead
produce a clearly marked draft QR for import-and-edit attempts; game acceptance of incomplete codes
is not yet verified, and this never counts as a successful recognition. The GUI optionally overrides
the screenshot style, runs recognition, and shows or downloads the existing outputs. It does not add
deck editing, history, accounts, or cloud upload. Use the `中 / EN` control in the top bar to switch
the complete interface language; the choice is remembered locally.

React and Vite are development dependencies only. Rebuild the packaged static assets after changing
`frontend/`:

```powershell
cd frontend
npm install
npm run build
```

The canonical format is specified in [Deck Text Format v1](docs/deck-text-format-v1.md).

## Documentation

- [Product requirements](prd.md)
- [Deck Text Format v1](docs/deck-text-format-v1.md)
- [Architecture](docs/architecture.md)
- [Development guide](docs/development.md)
- [Testing strategy](docs/testing.md)
- [Card database contract](docs/card-database-contract.md)
- [Data and licensing](docs/data-and-licensing.md)
- [Contributing](CONTRIBUTING.md)
- [Architecture decisions](docs/decisions/)
- [GUI visual reference specification](docs/brand-spec.md)
- [Game8 userscript](userscript/README.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Development setup

Python 3.11 or newer is required.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Run the quality gate:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m mypy src tests
.\.venv\Scripts\python -m pytest
```

## External card database

The project is designed to read an external `pokemon-tcg-pocket-database` release or checkout. It does not vendor a duplicate `cards.json` or official card artwork.

The expected development data path is currently:

```text
H:\CodexCode\ptcgp-database\dist
```

This path is an example only; pass another release with `--database-path` or
set `PTCGP_DATABASE_PATH`.

The current local release has known cross-file version skew. The baseline reads `cards.json`,
`sets.json`, and `images/cards-by-set`; it does not use the bundled SQLite snapshot as an
authoritative source. See the [card database contract](docs/card-database-contract.md).

## License status

No license has been selected for this repository yet. Third-party database code, metadata, model weights, and Pokémon artwork retain their own licenses and rights. See [Data and licensing](docs/data-and-licensing.md) and the retained [third-party notices](THIRD_PARTY_NOTICES.md).
