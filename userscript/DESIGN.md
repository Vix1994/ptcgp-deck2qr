# Game8 userscript design system

## Positioning

- Narrative role: a quiet utility attached to each `Deck Card List`, not a competing article CTA.
- Viewing distance: laptop and phone reading distance.
- Visual temperature: restrained, dependable, and tool-like.
- Capacity: one inline action and one compact modal; no persistent side panel.

## Tokens and behavior

- Color: Game8-adjacent blue (`#1769aa`) for actions, neutral white/gray surfaces, semantic green
  and red only for validation.
- Typography: inherit the host page font so the control belongs beside the heading.
- Spacing: 4 px base rhythm with 8, 12, 16, 20, and 24 px steps.
- Radius: 7–9 px controls, 12–14 px modal surfaces.
- Shadow: one modal elevation only; inline actions remain flat.
- Motion: 140–160 ms ease-out entry and state transitions, disabled under reduced-motion
  preferences.

The userscript deliberately uses no Game8 or Pokemon logos and distributes no official card art.
