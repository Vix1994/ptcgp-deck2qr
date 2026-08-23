# ADR 0009: Validate recovered grid slots with artwork evidence

Status: accepted  
Date: 2026-08-23

## Context

A card whose border is partially covered can lose every acceptable contour even when most of its
illustration remains visible. The slot resolver already represented one missing contour in a regular
count-badge grid, but the pipeline treated that slot as diagnostic-only and rejected it before its
pixels could contribute recognition evidence.

Accepting a location from grid geometry alone would violate the fail-closed recognition boundary. A
ragged final row or an empty grid cell is not a card, and geometry cannot determine entity identity.

## Decision

- Strongly supported gaps, including grid edges, may be proposed for regular portrait `separate-cards`,
  `count-text`, and `count-badge` grids with at least three rows and columns and two complete rows.
- In regular multi-row `separate-cards` and `count-text` grids, direct contours locate slots but do
  not define the final artwork crop edges. One representative per physical slot establishes the
  dominant card size, and every crop is recentered on the global row/column anchors. Original
  proposal boxes remain in diagnostics.
- A proposed gap is cropped using the dominant grid geometry and matched only against the artwork
  ROI index.
- Recovered artwork uses a named strict score-and-entity-margin policy with no strong-match override.
- A recovered proposal that does not pass that policy is discarded before counting and aggregation;
  it remains visible in slot diagnostics.
- A recovered proposal that passes has direct visual entity evidence and may enter normal count,
  deck validation, and output processing.
- Edge gaps use the same rule: geometry only proposes a crop, and artwork evidence must independently
  prove that the location contains a recognizable card. Empty cells in ragged rows are discarded.

## Consequences

- A missing or broken outer contour no longer necessarily loses a card when its illustration is
  still clear and the surrounding grid is strongly regular.
- A slightly shortened or vertically shifted contour no longer shifts that card's proportional
  artwork ROI away from the illustration.
- Empty inferred cells cannot enter a deck merely because their position is plausible.
- Detection remains independent of card identity; the pipeline joins geometric and visual evidence.
- Severe artwork occlusion, missing rows, and two-row layouts still fail closed.
