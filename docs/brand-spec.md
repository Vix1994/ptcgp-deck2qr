# GUI visual reference specification

## Positioning

`ptcgp-deck2qr` is an independent local companion tool. Its GUI references the approachable,
tactile interface grammar of Pokémon TCG Pocket without presenting itself as an official Pokémon
product.

Reference sources:

- [Pokémon TCG Pocket official site](https://tcgpocket.pokemon.com/en-us/)
- [Official Google Play listing](https://play.google.com/store/apps/details?id=jp.pokemon.pokemontcgp)
- [The Pokémon Company product announcement](https://corporate.pokemon.co.jp/en/topics/detail/t-28/)

## Visual system

- Pale sky-blue workspace with clean white surfaces.
- Thin blue-gray borders, short soft shadows, and rounded panels with a controlled hierarchy.
- Desktop application shell with a white navigation bar and a 304 / fluid / 340 three-column
  recognition workspace. The recognition canvas remains the visual focus.
- Cyan is the only primary action color; green, amber, orange, and red are reserved for recognition
  diagnostics.
- Compact rounded energy selectors use the established eight energy colors.
- Motion is short and tactile: small lifts, button presses, and a restrained scan line during work.
- Chinese and English are complete interface locales. The compact top-bar switch persists the user's
  choice; neither locale falls back to mixed-language operational copy.
- Recognition details and canonical Deck Text are available on demand so the accepted 20/20 result
  and QR code remain visually dominant.

Current implementation reference: [`gui-bilingual-reference-v2.png`](gui-bilingual-reference-v2.png).

## Asset policy

The application ships no official Pokémon logo, character, card artwork, or application screenshot.
The neutral card-stack mark and geometric controls are original interface elements. User screenshots
and the external card database remain runtime inputs and are not committed to this repository. The
energy selector icons are the explicit, user-authorized exception described below.

The eight energy selector icons under `frontend/src/assets/energy/` were cropped from a visual
reference supplied by the user on 2026-08-23. The user explicitly confirmed that they hold or have
obtained the necessary rights and authorized these derived icon assets to be included in this
project. The source reference itself is not committed.
