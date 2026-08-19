# Card database contract

## Purpose

`ptcgp-deck2qr` consumes an external release of
`flibustier/pokemon-tcg-pocket-database`. The external database is authoritative; the generated
fingerprint index is only a rebuildable cache.

The development snapshot inspected during project initialization is located at:

```text
H:\CodexCode\ptcgp-database\dist
```

Runtime code and tests must not hard-code this machine-specific path.

## Authoritative inputs

The first recognition milestone may depend on:

```text
cards.json
sets.json
images/cards-by-set/{set}/{number}.webp
```

It must not require:

- `ptcgp.db`, because the inspected snapshot is stale and has an invalid foreign-key definition.
- `cards.extra.json`, because newer expansions are not covered consistently.
- Language-specific card lists, because their release timing and completeness may differ.
- `pullRates.json`, which is unrelated to screenshot identity.

## Identity mapping

The adapter exposes three distinct identities:

| Internal concept | Upstream source | Use |
|---|---|---|
| `CardPrintKey` | `(set, number)` | Canonical Deck Text reference |
| `CardVisualId` | `image` filename | Fingerprint/index deduplication |
| `CardEntityKey` | parsed image prefix plus six-digit entity number | Semantic card identity and future QR mapping |

For the inspected schema:

```text
set       string, for example A1, A1a, PROMO-A
number    positive integer, unique together with set
rarity    upstream rarity code
name      English display name in cards.json
image     local WebP filename
packs     optional list; absent for some promotional cards
```

Image names currently follow forms such as:

```text
cPK_10_000010_00_FUSHIGIDANE_C.webp
cTR_10_000170_00_NATSUME_U.webp
```

`cPK` maps to the Pokémon section and `cTR` maps to the Trainer section. Filename parsing is an
adapter concern and must fail with a schema error when an unknown form appears; consumers must not
slice filenames themselves.

## Adapter validation

Loading a release must verify and report all of the following before index construction:

1. Every `(set, number)` is unique.
2. Every card references a known set code.
3. Every card has a readable image at the predictable path.
4. Every filename can be parsed into a supported entity type and entity number.
5. Multiple print keys sharing a visual ID resolve to one semantic entity.
6. Set release dates used for canonical alias selection are valid.

Declared set counts are diagnostic rather than authoritative. The inspected release contains known
declared-count mismatches, so a mismatch should be surfaced in the source report but should not by
itself prevent loading otherwise valid card rows.

## Generated index manifest

Every index must record at least:

```text
index schema version
cards.json SHA-256
sets.json SHA-256
source version or Git commit when known
fingerprint algorithm versions and parameters
artwork crop policy version
card, visual, and rejected-row counts
```

Recognition must reject an index whose source hashes or schema version do not match and provide an
explicit rebuild instruction. Updating the external database and rebuilding the index must not
require recognition-core changes unless the upstream schema itself changes.

## Distribution boundary

Do not copy `cards.json`, the external SQLite file, or official card artwork into this repository or
the Python wheel. Tests use small hand-authored metadata and synthetic or rights-cleared images.
Local indexes and source manifests live below `data/index/` and remain ignored by Git.
