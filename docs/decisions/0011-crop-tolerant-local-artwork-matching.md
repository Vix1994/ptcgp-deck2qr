# ADR 0011: Align artwork locally instead of tuning exact crop coordinates

Status: accepted  
Date: 2026-08-24

## Context

ADR 0010 made the illustration the portrait-card identity signal, but a single proportional ROI was
still sensitive to detector boxes that moved or changed size by a few pixels. Fixing individual
screenshots by adjusting crop constants would couple matching accuracy to every upstream layout and
would keep regressing as overlays, borders, and screenshot resampling changed.

The supplied 4×5 screenshot also demonstrates two distinct failure modes: a shifted contour around
the first card in row two and a missing contour around an overlaid card at the upper right. The
detector can provide a useful approximate slot for both, but it cannot promise an exact artwork ROI.

## Decision

- A portrait slot is location evidence only. It is not required to be an exact full-card crop.
- Coarse retrieval fingerprints nine artwork views shifted by ±4% horizontally and vertically.
- Each recalled reference illustration is searched inside a wider upper-card window at five scales.
- Only the two best template locations receive the expensive 3×3 local comparison. The six strongest
  patches form the robust patch score, while the visible-patch count remains an explicit acceptance
  signal.
- After local reranking, only the leading four candidates receive ORB matching and RANSAC homography
  verification. This preserves independent local-feature evidence without applying it to the whole
  database or every recalled candidate.
- Full-card fingerprints do not act as an entity fallback. Weak artwork, insufficient visible patches,
  or a small different-entity margin still fails closed.
- The versioned reference artwork crop has one implementation shared by index building, shifted
  recall, and reference loading.

## Evidence

- Rights-cleared synthetic regressions cover an approximate slot shifted by 8 pixels horizontally
  and 7 pixels vertically, two covered artwork patches, destroyed artwork, and a blank inferred cell.
- Against the local 3,546-visual index, the supplied screenshot produces 20 accepted observations.
  Both the overlaid upper-right card and row-two first card resolve to entity `B3b-059`, with all nine
  local patches visible after alignment.
- On the same Windows development runtime, that screenshot took about 6.0 seconds before staged
  verification. Restricting robust patch scoring to the two best scales and ORB/RANSAC to the leading
  four candidates reduced it to about 2.9 seconds with a cold reference cache and 1.7 seconds warm.

These timings are engineering measurements, not a permanent performance guarantee.

## Consequences

- Small detector shifts, border damage, and bounded local overlays no longer require per-layout pixel
  exceptions.
- Recognition costs more than hash-only matching but remains within the existing NumPy/OpenCV
  dependency boundary and avoids a model runtime or service.
- The matcher still does not support arbitrary perspective, severe blur, or artwork that is mostly
  covered. A learned embedding or detector remains a future option only after a rights-cleared,
  labeled benchmark shows this classical pipeline is insufficient.
