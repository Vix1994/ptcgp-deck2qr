# Architecture

## Architectural objective

Keep image recognition, the canonical Deck model, and future QR encoding independently testable.

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

Future only:
deck.txt -> Deck model -> QR payload encoder -> QR renderer
```

## Module boundaries

### `decktext`

Owns the Deck model, syntax, parser, canonical writer, and deck validation. It must not import OpenCV, Pillow, NumPy, screenshot types, or future QR code.

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

For a strongly supported regular count-badge grid, the resolver may represent an interior missing
contour as a `grid-inferred` slot. Such a slot is diagnostic geometry only and must fail closed until
it has direct image evidence sufficient for recognition.

### `matching`

Builds fingerprints from unique visual assets, retrieves candidates, reranks them, and produces visual/entity evidence. It must not decide deck validity.

### `pipeline`

Coordinates the modules, aggregates accepted observations, validates the Deck, and writes output artifacts. It owns no recognition algorithm.

### `debug`

Renders `recognized.png` and serializes `recognition.json`. Diagnostic serialization must not be reused as the canonical Deck Text format.

### Future `qr`

Consumes only a validated Deck model. It must not import detection or matching code.

## Dependency direction

Allowed direction:

```text
pipeline -> detection
pipeline -> matching
pipeline -> carddb
pipeline -> decktext
detection -> shared low-level image types
matching -> carddb identities
debug -> recognition result DTOs
future qr -> decktext Deck model
```

Forbidden examples:

- `decktext` importing OpenCV.
- `matching` writing `deck.txt`.
- `qr` reading screenshot crops.
- `carddb` downloading data implicitly during recognition.
- Core code depending on a hard-coded local database path.

## Data and determinism

Generated recognition indexes are caches, not authoritative data. Every index must include the source database hash and algorithm version. A mismatched index must fail with a clear rebuild instruction.

Canonical Deck Text output must be deterministic across machines for the same Deck model and database release.

## Failure model

The pipeline fails closed:

- Detection failure is not a zero-card deck.
- Multiple proposals for one physical position are resolved before matching and counting.
- Duplicate `slot_id` values are a structural error, not extra copies of a card.
- A grid-inferred slot without direct proposal evidence cannot enter a valid Deck.
- A close top-two entity match is not accepted as top one.
- An unreadable quantity is not assumed to be one.
- A 19- or 21-card result does not produce a successful `deck.txt`.
- Print aliases may select a canonical print only when all aliases share the same semantic entity.

Partial results belong in `recognition.json`, `recognized.png`, and optionally `deck.partial.txt`.

## Dependency policy

The classical baseline uses NumPy, Pillow, and headless OpenCV. Large inference runtimes, external OCR engines, remote services, or persistent databases require measured baseline failures and an ADR.
