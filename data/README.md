# Local generated data

This directory is reserved for rebuildable local artifacts such as fingerprint indexes and source manifests.

Generated indexes belong under `data/index/` and are ignored by Git. An index must record:

- Deck index schema version.
- Source `cards.json` SHA-256.
- Source database version or Git commit when available.
- Fingerprint algorithm and parameters.
- Artwork crop policy version.
- Build timestamp for diagnostics only.

The authoritative card database and official card images must remain external to this repository.
