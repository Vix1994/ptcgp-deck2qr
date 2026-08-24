# Data and licensing

## Repository license

The original source code and documentation in `ptcgp-deck2qr` are licensed under the
[MIT License](../LICENSE). This license does not grant rights to third-party software, database
content, Pokémon artwork, names, logos, or trademarks.

## External card database

The current generated userscript index is derived from
[`flibustier/pokemon-tcg-pocket-database`](https://github.com/flibustier/pokemon-tcg-pocket-database)
version `2.9.1`, whose repository code and metadata are published under MIT. The exact
`dist/cards.json` input contained 3,761 cards and had SHA-256
`eea30451bdbcf70788fb8e188c7fbe69182f32fa7597fc12ee0272dc9f4e006a`.
The upstream copyright and complete MIT License are retained in
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

Pin or record a version/commit when consuming a newer release, and update the retained
notice whenever the generated index changes.

The project should normally read an external checkout or release path and generate a local index. It must not maintain a divergent authoritative card list.

The currently inspected local release is a distribution snapshot rather than a complete source
checkout. Its base card JSON is newer than some auxiliary artifacts. In particular,
`cards.extra.json` has incomplete coverage for newer sets and the bundled SQLite file is stale and
structurally unsuitable as an authoritative source. The adapter contract therefore uses the base
JSON and predictable image tree; see [`card-database-contract.md`](card-database-contract.md).

## Pokémon artwork and marks

Repository licenses on community databases do not necessarily grant redistribution rights to Pokémon artwork, names, logos, trademarks, or other official assets.

Default policy:

- Do not commit the full card image library.
- Do not package card artwork into Python wheels.
- Do not commit user screenshots without permission.
- Keep downloaded assets and indexes out of Git.
- Store source and hash manifests for locally built indexes.
- Review distribution rights before publishing derived indexes that may retain expressive image information.

## Scanner and model references

Public source without an explicit license is reference-only; do not copy or redistribute its code or weights. Ultralytics models and runtimes have their own copyleft/commercial licensing considerations and are not part of the baseline.

## Contributions

Contributors must identify the provenance and redistribution terms of any fixture, model, weight, template, or dataset added to the project. A URL alone is not permission.

This document records engineering policy and is not legal advice.
