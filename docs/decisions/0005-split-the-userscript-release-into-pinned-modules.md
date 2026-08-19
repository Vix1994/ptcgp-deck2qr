# ADR 0005: Split the userscript release into pinned modules

Status: Accepted

Date: 2026-08-20

Supersedes: the self-contained release shape in ADR 0004 and ADR 0003

## Context

The first public userscript bundled the page adapter, QR implementation, and compact
card index into one approximately 97 KB file. Tampermonkey could update it automatically,
but every parser or UI change replaced the card index even when that data was unchanged.

The public GitHub repository can host external userscript dependencies through Raw URLs.
Tampermonkey supports preloaded `@require` JavaScript and `@resource` data, including
subresource-integrity hashes.

## Decision

Publish the userscript as three artifacts:

- `game8-ptcgp-deck-qr.user.js`: a small installed loader;
- `game8-ptcgp-deck-qr.core.js`: the bundled parser, UI, and QR implementation; and
- `game8-ptcgp-deck-qr.card-map.json`: the generated card-print index.

The core exports one explicit `start(cardMap)` function. The loader obtains the card map
through `GM_getResourceText`, resolves the core from the userscript sandbox, and passes
the parsed resource into that function. Neither external module accesses screenshot
recognition internals.

The loader and metadata remain on the default branch so Tampermonkey can check for new
versions. Core and card-map URLs use immutable release tags and include generated
SHA-256 integrity fragments. The package version selects the core tag. The independent
`cardMapRelease` field selects the card-map tag, so code-only releases can keep the same
cached map URL.

Every release must be built and tested before its `vX.Y.Z` tag is created. The tag must
exist before that version is offered through the default-branch update metadata.

## Consequences

Positive:

- The installed loader is about 1.6 KB.
- Parser, UI, or QR changes update only the approximately 43 KB core module.
- The approximately 77 KB card map changes only when the source database changes.
- Integrity mismatches fail closed before external code or data is used.
- The release contract and integrity values are verified by automated tests.

Negative:

- Initial installation needs GitHub Raw access for two tagged resources.
- Publishing now requires coordinated build, tag, and default-branch metadata steps.
- A missing tag makes that userscript version uninstallable even if its loader exists.
- Tampermonkey's cached external-resource behavior is part of the distribution contract.

## Alternatives considered

### Keep the self-contained bundle

Rejected for ongoing releases because small code changes would continue replacing the
unchanged card index.

### Import another installed userscript

Rejected because Tampermonkey does not provide a supported module registry or reliable
execution ordering between independently installed scripts.

### Fetch mutable modules at page runtime

Rejected because it would bypass Tampermonkey's resource cache and integrity handling,
be more exposed to CSP and CORS behavior, and allow code to drift without a userscript
version change.
