# Architecture

## Architectural objective

Keep image recognition, the canonical Deck model, and downstream QR encoding independently testable.

```text
Screenshot + explicit energy
        |
        v
Region proposals -> slot resolution -> style/count extraction -> visual matcher
        |                                  |
        +------------ Recognition ---------+
                         |
                         v
                  validated Deck model
                         |
                         v
                Deck Text parser/writer
                         |
                         v
                      deck.txt
                         |
                         v
                 QR input adapter
                         |
                         v
              Deck Code -> QR renderer
```

The optional local GUI is a presentation adapter around the same pipeline:

```text
React UI -> local Python HTTP adapter -> pipeline.recognize_image
                                           |
                                           +-> deck.txt + diagnostics
                                           +-> validated or review-draft QR input
                                               -> browser Deck Code + QR
```

## Module boundaries

### `decktext`

Owns the Deck model, syntax, parser, canonical writer, and deck validation. It must not import OpenCV, Pillow, NumPy, screenshot types, or QR code libraries.

### `carddb`

Adapts the external `pokemon-tcg-pocket-database` schema into three identities:

```text
CardPrint  = set + number
CardVisual = image filename
CardEntity = PK/TR + numeric entity ID
```

It owns alias selection and database source manifests. It must not own the upstream data.
Its authoritative inputs and validation rules are defined in
[`card-database-contract.md`](card-database-contract.md).

### `detection`

Finds raw card or artwork proposals, resolves them into unique physical card slots, classifies
screenshot style, and extracts count regions. A contour is evidence, not a card. The matcher and
counter may consume `CardSlot` values only; they must never consume raw `RegionProposal` values.

The `SlotResolver` owns proposal clustering, dominant card geometry, global row/column anchors, and
stable `slot_id` assignment. It is blind to Card IDs. A card repeated in two positions remains two
slots, while nested contours for one physical position become one slot.

For regular multi-row `separate-cards` and `count-text` grids, contour boxes locate physical slots
but the resolver normalizes their final crops to the dominant representative size and global grid
centers. This keeps proportional artwork ROIs aligned when one border contour is short or shifted;
the original proposal boxes remain available for diagnostics.

For a strongly supported regular portrait grid, the resolver may represent an interior or edge missing
contour as a `grid-inferred` slot. Such a slot is only a geometric crop candidate. The pipeline
discards it unless its artwork independently passes the strict recovered-slot visual and entity
margin policy; an accepted recovered slot then has direct image evidence sufficient for recognition.

### `matching`

Builds fingerprints from unique visual assets, retrieves candidates, reranks them, and produces
visual/entity evidence. Portrait screenshot styles use artwork as the entity signal; complete-card
fingerprints do not override an ambiguous artwork decision. Their slot rectangle is deliberately
approximate rather than an exact identity ROI. Shifted artwork hashes perform coarse recall, a wider
window supplies five-scale local alignment, and the six strongest cells of a 3×3 comparison make the
score tolerant of bounded occlusion. ORB matches and a RANSAC homography verify only the leading
candidates after the cheaper local rerank. Hash score, patch visibility, feature inliers, and
distinct-entity margin remain separate diagnostics. It must not decide deck validity.

### `pipeline`

Coordinates the modules, aggregates accepted observations, validates the Deck, and writes output artifacts. It owns no recognition algorithm.

### `gui` and `webgui`

`gui` serves the compiled React application, adapts one local request into the existing pipeline call,
and exposes QR input for an accepted Deck or an explicitly marked 18-20 card review draft. `webgui`
contains generated static build artifacts.
Neither layer owns recognition, Deck validation, or canonical writing. The editable frontend source
lives under `frontend/`; it delegates the Deck Code format and QR rendering to the pinned
`ptcgp-deckcode` package.

### `debug`

Renders `recognized.png` and serializes `recognition.json`. Diagnostic serialization must not be reused as the canonical Deck Text format.

### `qr`

Consumes only a Deck model and the active card database. Its normal path requires a validated
20-card Deck; its explicit review path accepts only a structurally validated 18-20 card draft. It
resolves print identities for the pinned browser Deck Code encoder and must not import detection or
matching code.

## Dependency direction

Allowed direction:

```text
pipeline -> detection
pipeline -> matching
pipeline -> carddb
pipeline -> decktext
gui -> pipeline
detection -> shared low-level image types
matching -> carddb identities
debug -> recognition result DTOs
qr -> decktext Deck model
qr -> carddb
```

Forbidden examples:

- `decktext` importing OpenCV.
- `matching` writing `deck.txt`.
- `qr` reading screenshot crops.
- `carddb` downloading data implicitly during recognition.
- Core code depending on a hard-coded local database path.
- React code reproducing recognition, validation, or Deck Text rules.

## Data and determinism

Generated recognition indexes are caches, not authoritative data. Every index must include the source database hash and algorithm version. A mismatched index must fail with a clear rebuild instruction.

Canonical Deck Text output must be deterministic across machines for the same Deck model and database release.

## Failure model

The pipeline fails closed:

- Detection failure is not a zero-card deck.
- Multiple proposals for one physical position are resolved before matching and counting.
- Duplicate `slot_id` values are a structural error, not extra copies of a card.
- A grid-inferred slot cannot enter a valid Deck unless its artwork passes the strict recovered-slot
  visual and entity-margin policy.
- A close top-two entity match is not accepted as top one.
- An unreadable quantity is not assumed to be one.
- A 19- or 21-card result does not produce a successful `deck.txt`.
- Print aliases may select a canonical print only when all aliases share the same semantic entity.

Partial results belong in `recognition.json`, `recognized.png`, and optionally `deck.partial.txt`.

## Dependency policy

The classical baseline uses NumPy, Pillow, and headless OpenCV. Large inference runtimes, external OCR engines, remote services, or persistent databases require measured baseline failures and an ADR.
