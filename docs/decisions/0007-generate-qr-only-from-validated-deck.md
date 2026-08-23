# ADR 0007: Generate QR only from a validated Deck

Status: Accepted

Supersedes: the QR-scope deferral in ADR 0006; the React presentation-layer boundary remains in force.

## Context

The local GUI should proceed directly from successful screenshot recognition to a scannable deck QR.
The repository already pins and tests `ptcgp-deckcode` 2.0.0 in the independent Game8 userscript.
Its payload format is reverse-engineered and its card identifier is derived from the external database
image identity.

QR generation must not weaken the recognition fail-closed policy or create a dependency from the QR
encoder to screenshots, OpenCV, slot geometry, confidence scores, or diagnostic JSON.

## Decision

- Add a Python `qr` adapter that consumes only a validated Deck and the active `CardDatabase`.
- Resolve every Deck Text print through that database and emit only print ID, image identity, count,
  name, and energies as browser-safe QR input.
- Reject missing mappings, malformed deck-builder identities, totals other than 20, and more than two
  copies of the same semantic entity.
- Use the already adopted, pinned `ptcgp-deckcode` 2.0.0 package in the React build for Deck Code
  encoding and QR rendering.
- Start QR generation automatically after a successful recognition response. Partial or rejected
  recognition results never receive QR input and never generate a QR.
- Render the QR locally in the browser and offer PNG download and Deck Code copy. No deck data is sent
  to a remote service.

## Consequences

- Screenshot recognition remains independently testable and continues to produce canonical Deck Text.
- The QR layer is deterministic for a validated Deck and database release.
- The frontend bundle grows because it includes the QR renderer.
- A recognition can succeed while QR generation reports a separate mapping or rendering failure.
- The generated payload relies on a reverse-engineered third-party format and requires real-device
  scanning tests in addition to round-trip software tests.

## Alternatives considered

- **Encode from recognition diagnostics:** rejected because it couples QR output to visual internals.
- **Maintain a second card-number map:** rejected because it would compete with the external database.
- **Add a Python QR dependency and duplicate the encoder:** rejected because the same pinned encoder is
  already used and tested in the userscript.
- **Generate QR for partial decks:** rejected because ambiguity must fail closed.
