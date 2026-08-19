# Repository working agreement

## Read before changing code

1. Read `prd.md` for product scope.
2. Read `docs/deck-text-format-v1.md` before changing the deck model or text format.
3. Read `docs/architecture.md` before adding a dependency or crossing a module boundary.
4. Record material architectural decisions as an ADR under `docs/decisions/`.

## Current product boundary

The current milestone is:

```text
screenshot + explicit energy input -> Deck model -> deck.txt
```

Do not add QR encoding to the recognition pipeline during this milestone. The future QR layer must consume the Deck model or canonical Deck Text; it must not depend on OpenCV, screenshot layouts, or recognition internals.

## Engineering rules

- Python 3.11 or newer.
- Use the `src` package layout.
- Keep public functions and dataclasses fully typed.
- Prefer pure functions at parsing, normalization, validation, and scoring boundaries.
- Recognition must fail closed: an ambiguous entity or count must not silently become an accepted deck.
- Keep detection confidence, visual match confidence, entity confidence, and count confidence separate.
- Do not treat a raw hash similarity as a calibrated probability.
- Do not copy or maintain a second authoritative `cards.json`.
- Generated indexes must include source hashes and remain rebuildable from the external card database.
- Do not commit official card images, downloaded databases, generated indexes, or user screenshots without explicit rights.
- Do not add PyTorch, TensorFlow, Ultralytics, ONNX Runtime, CLIP, OCR engines, or a service dependency without an ADR and measured evidence that the classical baseline is insufficient.

## Required checks

Before handing off a change, run:

```text
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest
```

Format intentionally with:

```text
python -m ruff format .
python -m ruff check --fix .
```

## Test expectations

- Every bug fix requires a regression test.
- Deck Text parser and writer changes require round-trip and canonical-output tests.
- Database mapping changes require schema, identity, and alias tests.
- Recognition changes require fixture provenance and separate assertions for detection, entity, and count.
- Never lower a confidence threshold solely to make a fixture pass.
