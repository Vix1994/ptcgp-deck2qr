# Data and licensing

## Repository license

No license has been selected for `ptcgp-deck2qr` yet. Add a project `LICENSE` only after the maintainer chooses one intentionally.

## External card database

The planned data source is `flibustier/pokemon-tcg-pocket-database`, whose repository code and metadata are published under MIT at the time of project planning. Pin or record a version/commit when consuming it, and preserve required notices when copying licensed material.

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
