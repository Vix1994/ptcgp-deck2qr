# ADR 0001: Deck Text as the system boundary

Status: Accepted  
Date: 2026-08-16

## Context

The product eventually needs both screenshot recognition and PTCGP QR generation. Screenshot recognition is probabilistic and layout-dependent, while QR payload encoding is deterministic and may change as the game evolves.

Implementing them as one pipeline would make recognition tests depend on reverse-engineered QR details and would make QR changes affect image-processing code.

## Decision

The current milestone ends at a validated Deck model and canonical Deck Text Format v1 document.

```text
screenshot + explicit energy -> recognition -> Deck -> deck.txt
```

A future QR module will consume the same Deck model or parse canonical Deck Text:

```text
deck.txt -> Deck -> payload -> QR
```

The Deck Text parser, writer, and domain model must remain independent of image and QR dependencies.

## Consequences

Positive:

- Recognition can be evaluated without a phone or QR scanner.
- Users can inspect and correct the intermediate result.
- QR implementations can be swapped or versioned independently.
- Other future inputs can produce the same Deck Text.

Negative:

- The project must maintain a documented text compatibility contract.
- End-to-end screenshot-to-QR requires an additional parsing boundary.
- Print aliases need deterministic canonicalization even though QR uses semantic entities.

## Alternatives considered

### Emit only internal JSON

Rejected because the primary intermediate should be readable and easy to edit or share. Diagnostic JSON remains a separate output.

### Generate QR directly from recognition

Rejected because it couples probabilistic and deterministic subsystems and makes incorrect automatic acceptance harder to inspect.
