# ADR 0004: Distribute the userscript through GitHub Raw

Status: Accepted  
Date: 2026-08-19

## Context

Manually replacing the complete userscript for every fix is inconvenient. Tampermonkey
can compare a remote `@version` through `@updateURL` and retrieve a newer script through
`@downloadURL`. The project is small and is published as a public GitHub repository.

The normal version check should not need to download the complete bundled card index.

## Decision

Publish two generated release artifacts on the default branch:

- `game8-ptcgp-deck-qr.meta.js`, containing only the userscript metadata header; and
- `game8-ptcgp-deck-qr.user.js`, containing the same header and the self-contained
  browser bundle.

Both URLs use `raw.githubusercontent.com/Vix1994/ptcgp-deck2qr/main`. Every functional
release must increase the package and userscript version. The build creates both files
from the same metadata template so their versions and update URLs cannot drift.

The current bundle stays self-contained. If it is split later, executable dependencies
must use immutable tag or commit URLs with integrity hashes rather than mutable branch
URLs.

## Consequences

Positive:

- Users install once and receive normal Tampermonkey update checks.
- Routine checks fetch only a small metadata file.
- The installed script and source repository are directly auditable.
- Release metadata is reproducible from source.

Negative:

- Distribution depends on GitHub Raw availability and caching.
- A release is incomplete if the version is not increased before pushing.
- The public repository intentionally has no open-source license until one is selected.

## Alternatives considered

### Continue manual copy and paste

Rejected because each fix would require users to replace the full script manually.

### Load mutable modules from the default branch

Rejected because cached external resources could drift independently from the installed
userscript version and cannot be pinned with a stable integrity hash.

### Operate a separate update service

Rejected because the current project does not need additional hosting or service
infrastructure.

