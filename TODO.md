# MVP implementation TODO

Owner split:

- Main agent: task definition, acceptance criteria, review, and final verification.
- Implementation subagent: code and tests only.
- `prd.md` and normative documents are inputs. Do not rewrite product scope while implementing.
- QR / Deck Code generation is outside this milestone.

## TODO 1 — Deck domain and Deck Text v1

- [x] Define typed immutable values for energy, print identity, card entry, and deck.
- [x] Implement strict Deck Text v1 parsing and deterministic canonical writing.
- [x] Keep syntax validation separate from game-deck validation.
- [x] Reject unknown fields, malformed IDs, invalid energy, duplicate metadata, wrong sections,
      invalid counts, unresolved cards, and decks whose total is not 20.

Acceptance:

- Canonical output follows `docs/deck-text-format-v1.md` byte-for-byte.
- Parse/write round trips preserve the Deck model.
- Domain and Deck Text modules do not import imaging or QR dependencies.
- Unit tests cover valid, invalid, canonicalization, and round-trip cases.

## TODO 2 — External card database and fingerprint index

- [x] Load externally supplied `cards.json`, `sets.json`, and `images/cards-by-set` paths.
- [x] Map `(set, number)`, visual filename, and parsed PK/TR entity identity without maintaining a
      second authoritative card list.
- [x] Validate schema, identity uniqueness, set references, image existence, filename structure,
      and alias/entity consistency.
- [x] Build a deterministic, rebuildable classical fingerprint index with a source manifest.
- [x] Reject stale or incompatible indexes with an actionable rebuild message.

Acceptance:

- No machine-specific database path is embedded in package code.
- `cards.extra.json` and the bundled SQLite snapshot are not required.
- The manifest records source hashes, schema/algorithm versions, parameters, and row counts.
- Tests use a minimal hand-authored database fixture; official card data/images are not committed.

## TODO 3 — Screenshot regions, styles, and counts

- [x] Detect candidate card/full-artwork regions after scale normalization.
- [x] Represent the four required styles: repeated card instances, `Quantity`, `×N`, and
      bottom-right count badge.
- [x] Bind each count region to one detected card region.
- [x] Limit count recognition to `1` and `2`; return `ambiguous-count` instead of guessing.
- [x] Preserve bounding boxes, layout/style evidence, crop quality, and count evidence.

Acceptance:

- Detection works from geometry/image evidence rather than one hard-coded screenshot resolution.
- Synthetic fixtures exercise all four style/count paths.
- Detection and count failures remain distinguishable in diagnostic results.

## TODO 4 — Matching, pipeline, CLI, and debug artifacts

- [x] Retrieve top-k candidates using perceptual/color fingerprints and rerank with classical
      image similarity; use ORB only where it provides measured value.
- [x] Keep visual-match scores, entity margin, crop quality, and count confidence separate.
- [x] Reject low-confidence or close cross-entity matches instead of forcing top-1.
- [x] Implement index build and `ptcgp-deck2qr recognize` CLI flows with explicit energy,
      database path, index/output path, and useful exit codes.
- [x] Produce `deck.txt` only for a fully valid result; always preserve useful failure diagnostics
      in `recognition.json` and `recognized.png` where an input image can be read.

Acceptance:

- Successful recognition produces deterministic `deck.txt`, `recognition.json`, and
  `recognized.png`.
- Failed recognition cannot be reported as a valid deck and does not silently invent cards/counts.
- CLI help, invalid-input behavior, and a synthetic end-to-end flow are tested.
- No QR, heavyweight model, unrestricted OCR, remote service, or implicit network request is added.

## TODO 5 — Verification and handoff

- [x] Add unit, component, CLI, and synthetic end-to-end tests with documented fixture provenance.
- [x] Run the four user-supplied screenshots as non-committed smoke tests and report detection,
      matching, count, and final-deck status separately for each.
- [x] Update only implementation-facing README/development/testing documentation that became
      inaccurate; do not rewrite the PRD.
- [x] Pass Ruff lint, Ruff format check, Mypy strict, Pytest, coverage threshold, and `pip check`.

Acceptance:

- Test evidence covers each preceding TODO rather than only package importability.
- Smoke-test failures and unsupported layouts are reported honestly as known limitations.
- The main agent completes an independent diff review and reruns the full quality gate.

## Review disposition

Status: accepted by the main agent on 2026-08-17.

Independent review evidence:

- Ruff lint and format, Mypy strict, and `pip check` passed.
- Pytest passed 62 tests with 93.11% branch-aware coverage.
- All four synthetic styles pass automatic detection, count extraction, matching, and pipeline
  tests.
- User sample 1 (`separate-cards`) and sample 3 (`count-text`) produced correct validated 20-card
  `deck.txt` files.
- User sample 2 (`quantity-label`) and sample 4 (`count-badge`) were safely rejected because some
  entities did not meet their stricter style-specific match policies. Detection and count extraction
  succeeded; diagnostics retained top-k evidence. Known wrong candidates were verified as rejected.

Known MVP limitation: artwork-only and badge-contaminated crops still need better entity recall.
This limitation does not weaken the fail-closed acceptance rules and is suitable follow-up work.
