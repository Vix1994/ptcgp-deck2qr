# ADR 0002: Resolve region proposals into physical card slots

Status: accepted  
Date: 2026-08-17

## Context

OpenCV contours are not card identities. One physical card can produce an outer border, an inner
border, and an artwork contour. Treating each contour as a card caused a real screenshot to produce
21 observations from a 20-card grid: two nested proposals for one Magnezone were both matched and
counted.

Adding more pairwise overlap thresholds to the old deduplication function would make correctness
depend on a growing list of local exceptions. Deduplicating by recognized Card ID would also be
wrong because a legal screenshot can contain two spatially separate copies of the same card.

## Decision

Detection has two explicit semantic stages:

```text
image -> RegionProposal[] -> SlotResolver -> CardSlot[] -> matcher/count
```

- `RegionProposal` is immutable contour evidence. Multiple proposals may describe one card.
- `SlotResolver` estimates dominant card geometry, clusters normalized centers, assigns global row
  and column anchors, and emits stable spatial `slot_id` values.
- `CardSlot` represents one physical card position. Only slots may enter matching and counting.
- Proposal clustering is independent of Card ID and recognized quantity.
- The pipeline treats duplicate slot IDs as a structural failure.
- A strongly supported regular badge grid may yield an interior `grid-inferred` slot when a contour
  is missing. It is retained for diagnostics but cannot contribute to a valid Deck without direct
  recognition evidence.
- Debug output retains both proposals and resolved slots so every merge or inference is auditable.

## Consequences

- Nested borders no longer inflate card counts.
- Repeated copies of the same card remain independent when they occupy different positions.
- Row and column identities remain stable when one row is missing a contour.
- Detection diagnostics become larger but explain why proposals were merged or a slot was inferred.
- Slot resolution is now a first-class component with dedicated geometry and regression tests.

## Alternatives rejected

### Add more IoU or containment thresholds

This addresses individual shapes but leaves raw contours as the domain object and accumulates local
rules.

### Deduplicate matching results by Card ID

This would collapse legitimate repeated cards and couples spatial detection to database identity.

### Cap aggregated card counts at two

This hides detection errors, can silently change the user's deck, and violates fail-closed behavior.
