# ptcgp-deck2qr

Convert a structured Pokémon TCG Pocket deck screenshot into canonical Deck Text and, through the
local GUI, a Deck Code and QR image.

> Status: pre-alpha local MVP.

## Purpose

The recognition pipeline converts a screenshot plus explicit energy selection into a validated Deck
model and canonical `deck.txt`. The optional local GUI then generates a Deck Code and QR from that
model. Ambiguous cards or counts fail closed, and QR encoding remains independent of recognition.

The current recognizer accepts structured deck-list screenshots in PNG, JPEG, or WebP format. It is
not intended for photographs, heavily tilted cards, or severely obscured layouts. Supported energies
are `grass`, `fire`, `water`, `lightning`, `psychic`, `fighting`, `darkness`, and `metal`.

## Usage

Python 3.11 or newer and an external
[`pokemon-tcg-pocket-database`](https://github.com/flibustier/pokemon-tcg-pocket-database/releases/latest)
release are required. Its `dist` directory must contain `cards.json`, `sets.json`, and
`images/cards-by-set/{set}/{number}.webp`.

Install the project and point it at the extracted `dist` directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
$env:PTCGP_DATABASE_PATH = "H:\path\to\pokemon-tcg-pocket-database\dist"
```

Build the local fingerprint index once:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe build-index
```

Recognize a screenshot:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe recognize deck.png `
  --energy lightning `
  --index-path data\index\fingerprint.json `
  --output-dir output
```

Successful recognition writes `deck.txt`, `recognition.json`, and `recognized.png`. Rejected
recognition still writes diagnostics and may write `deck.partial.txt`.

Launch the local browser GUI:

```powershell
.\.venv\Scripts\ptcgp-deck2qr.exe gui
```

The GUI accepts selected, dragged, or pasted images and can download the QR PNG or copy the Deck
Code. A reliable 18- or 19-card result may produce a clearly marked draft QR; recognition still
counts as failed, and game acceptance of an incomplete code is not verified.

POSIX setup and development commands are in the [development guide](docs/development.md).

## Optional Game8 userscript

The independent [Game8 Tampermonkey adapter](userscript/README.md) adds a `生成 QR` button to
supported Game8 deck lists and generates the Deck Code and QR locally in the browser.

[Install the current userscript from GitHub Raw](https://raw.githubusercontent.com/Vix1994/ptcgp-deck2qr/main/userscript/release/game8-ptcgp-deck-qr.user.js).

The userscript validates a complete 20-card list and updates through Tampermonkey. It is independent
of screenshot recognition.

## Data and project statements

- Processing and QR generation are local; the project does not provide a cloud service or user
  accounts.
- The external card database, official card images, user screenshots, and generated recognition
  indexes are not distributed in the Python package.
- The local GUI uses the database release selected by `--database-path` or
  `PTCGP_DATABASE_PATH`; it does not fetch a floating database through the QR encoder.
- The Game8 userscript contains a compact source-hashed mapping derived from database version
  `2.9.1`; it does not contain the complete upstream database or card artwork.
- Pokémon names, artwork, logos, and trademarks belong to their respective rights holders. This is
  an unofficial community project and is not affiliated with or endorsed by The Pokémon Company.

For details, see [Deck Text Format v1](docs/deck-text-format-v1.md),
[architecture](docs/architecture.md), [product requirements](prd.md), the
[card database contract](docs/card-database-contract.md), and [data and licensing](docs/data-and-licensing.md).

## Referenced projects

- [`flibustier/pokemon-tcg-pocket-database`](https://github.com/flibustier/pokemon-tcg-pocket-database)
  supplies external card metadata and image identities. Its repository code and metadata are MIT
  licensed; artwork may have separate rights.
- [`ptcgp-deckcode` 2.0.0](https://github.com/Nirostar/ptcgp-deck-qr/tree/master/packages/deckcode)
  implements the community-reverse-engineered Deck Code format under the MIT License.
- [`qrcode` 1.5.4](https://www.npmjs.com/package/qrcode) renders QR images and is distributed under
  the MIT License.

Exact versions, source hashes, copyright notices, and retained license text are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## License

`ptcgp-deck2qr` is licensed under the [MIT License](LICENSE). Third-party projects, data, Pokémon
artwork, names, logos, and trademarks retain their own licenses and rights as described above.
