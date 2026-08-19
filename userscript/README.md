# Game8 PTCGP Deck QR userscript

Tampermonkey userscript that adds a `生成 QR` button beside each `Deck Card List`
heading on Game8 Pokémon TCG Pocket guide pages. It reads the structured card table,
validates exactly 20 cards, lets the user confirm energy types, and creates a PTCGP
deck-share QR code locally in the browser.

## Install or update

1. Install Tampermonkey in the browser.
2. Open the [Raw userscript][install] and confirm installation in Tampermonkey.
3. Reload the Game8 page.

Tampermonkey checks the small `game8-ptcgp-deck-qr.meta.js` file and downloads the full
userscript only after its version increases. Existing manual installations need to
install the Raw release once to receive these automatic updates.

Version 0.1.1 supports Game8's current split markup: the card print identity is read
from the image `alt`, while the `×1` or `×2` quantity is read from the surrounding
table cell.

The release is self-contained. It does not fetch JavaScript or a full card database
from GitHub at runtime, and it does not upload the deck list.

## Behavior and failure rules

- A button is added independently to every matching deck-list section.
- Card prints are resolved by Game8 set code and collector number.
- The parser fails closed if a print cannot be resolved, a quantity is missing, or the
  total is not exactly 20 cards.
- Energy types detected in the nearby Game8 section are preselected and remain
  editable before QR generation.
- The PNG QR and deck code are generated locally with `ptcgp-deckcode`.

The QR payload format is reverse-engineered and is not an official Pokémon API.

## Development

Node.js 20 or newer is recommended.

```powershell
cd userscript
npm ci
npm run check
```

Rebuild the compact print-to-deck-number index from an external database checkout:

```powershell
npm run build:card-map -- --database-path H:\CodexCode\ptcgp-database\dist\cards.json
npm run check
```

The generated index records the source SHA-256 and card count. Do not hand-edit it or
commit the source database and official card images.

The bundled compact index was generated from
[`flibustier/pokemon-tcg-pocket-database`][database] version `2.9.1`. Its upstream
copyright and MIT License are retained in the repository's
[third-party notices](../THIRD_PARTY_NOTICES.md).

[install]: https://raw.githubusercontent.com/Vix1994/ptcgp-deck2qr/main/userscript/release/game8-ptcgp-deck-qr.user.js
[database]: https://github.com/flibustier/pokemon-tcg-pocket-database
