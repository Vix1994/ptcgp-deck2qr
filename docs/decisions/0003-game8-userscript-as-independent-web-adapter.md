# ADR 0003: Game8 userscript as an independent web adapter

Status: Accepted  
Date: 2026-08-19

## Context

Game8 publishes Pokémon TCG Pocket deck lists as structured HTML but does not offer a
deck-share QR action. Users want a lightweight browser-side action without routing the
page through screenshot recognition or installing a service.

The browser still needs deterministic card-print identifiers. Shipping the complete
external card database, card images, or a second hand-maintained `cards.json` would be
unnecessarily large and would create a competing source of truth.

## Decision

Implement Game8 support as a self-contained Tampermonkey adapter under `userscript/`,
separate from the Python screenshot-recognition pipeline.

The adapter will:

1. parse only the structured Game8 deck-list section adjacent to the selected heading;
2. normalize it into explicit card-print and count records and require a 20-card total;
3. resolve prints through a generated compact `set-number -> deckBuilderNr` index;
4. ask the user to confirm energy types; and
5. pass only the validated deck numbers and energies to the QR encoder.

The compact index is rebuildable from the external card database and records its source
hash. The browser release bundles the pinned `ptcgp-deckcode` dependency and the compact
index, so normal use makes no runtime code or database request.

This is an additional structured-web input adapter, not QR encoding added to screenshot
recognition. It does not import OpenCV, recognition layouts, confidences, or screenshot
internals.

## Consequences

Positive:

- The button works entirely in the current Game8 page and remains usable offline after
  the userscript has loaded.
- There is no service, uploaded deck data, full runtime database, or official artwork.
- DOM parsing, print resolution, 20-card validation, and QR encoding can be tested
  separately.
- A Game8 markup change fails closed instead of silently producing a different deck.

Negative:

- Game8 markup changes may require a userscript update.
- The compact map must be rebuilt for newly released card prints.
- The deck-share payload relies on a reverse-engineered third-party implementation.
- Without an `@updateURL`, users replace the installed userscript manually.

## Alternatives considered

### Load JavaScript directly from GitHub

Rejected for the release build because it adds availability and supply-chain risk and
makes the installed script change without an explicit release rebuild.

### Ship the complete card database

Rejected because the userscript only needs the print-to-deck-number relation. A compact,
source-hashed generated index is sufficient and rebuildable.

### Reuse screenshot recognition on the page

Rejected because Game8 already exposes structured card identity and quantity evidence.
Image recognition would be larger, slower, probabilistic, and coupled to page artwork.

