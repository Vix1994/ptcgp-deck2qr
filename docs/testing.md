# Testing strategy

## Test layers

### Unit tests

Fast, deterministic tests for:

- Deck Text parsing and canonical writing.
- Deck validation.
- Database filename and identity parsing.
- Print-alias selection.
- Hash and score calculations.
- Count-template classification.

### Component tests

Tests for one module using controlled fixtures:

- Region detection against synthetic grids.
- Artwork-crop matching against locally generated transforms.
- Database adapter against a minimal, hand-authored schema fixture.
- Debug JSON schema and annotation placement.

### Integration tests

Optional tests that use an externally configured database and rights-cleared screenshot fixtures. They verify:

- Index build and source manifest validation.
- Screenshot to recognition result.
- Recognition result to canonical `deck.txt`.
- Deterministic repeated execution.

Integration tests must skip with a clear reason when external data is unavailable.

### Manual acceptance

The initial four screenshot styles require manual visual review of `recognized.png` in addition to automated assertions. Later QR work will add an explicit current-game scan gate.

## Core invariants

Tests must preserve these invariants:

- A successful Deck contains exactly 20 cards.
- Energy is explicit and never inferred from the recognized cards.
- Ambiguous entity or count results do not produce a successful Deck Text.
- Canonical writer output parses back into an equivalent Deck model.
- Writing the same Deck twice produces identical bytes.
- All print aliases selected for one visual resolve to the same semantic entity.

## Recognition metrics

Track separately:

- Detection recall and false regions.
- Visual top-1 and top-k recall.
- Entity auto-accept precision.
- Entity rejection rate.
- Count accuracy.
- End-to-end valid 20-card deck rate.

The primary safety metric is entity auto-accept precision. Never hide a regression by lowering the acceptance threshold or reporting only top-k recall.

## Fixture policy

See `tests/fixtures/README.md`. Screenshot and card-image provenance is part of the test data, not optional documentation.

## Coverage

The initial coverage floor is 90% for executable package code. Coverage is a guardrail, not a substitute for meaningful failure-case tests.
