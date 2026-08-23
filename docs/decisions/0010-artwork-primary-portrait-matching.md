# ADR 0010: Use artwork as the primary portrait-card identity signal

Status: accepted  
Date: 2026-08-23

## Context

Portrait screenshot styles previously matched the entire detected card crop. A decorative overlay,
painted corner, missing border, language difference, or lower rules text could therefore change the
same entity's global fingerprint. The index already contained separate artwork fingerprints, but
only landscape `quantity-label` thumbnails and grid-recovered crops consumed them.

Using the complete card as a fallback after weak artwork would undermine the change: an occluded or
text-heavy crop could override an ambiguous illustration and silently choose an entity.

## Decision

- Every detected portrait card in `separate-cards`, `count-text`, and `count-badge` styles is matched
  against the artwork feature family first and exclusively for entity acceptance.
- The named portrait-artwork policy requires both a minimum visual score and a distinct-entity
  margin and has no strong-match override.
- Complete-card fingerprints remain in the rebuildable index for compatibility, diagnostics, and
  explicit low-level matching, but the screenshot pipeline does not use them as an entity fallback.
- `quantity-label` retains its separately named artwork policy because its input crop is already a
  landscape illustration rather than a portrait card.
- Grid-recovered crops retain an even stricter artwork policy because they lack contour evidence.

## Consequences

- Card borders, corners, language, and lower text no longer drive normal portrait entity decisions.
- A visible and distinctive illustration can identify a card whose outer contour is missing.
- Artwork that is itself covered, visually weak, or too similar to another entity remains ambiguous
  and is available only through the existing review-draft path.
- No new runtime, external service, or authoritative card data is introduced.
