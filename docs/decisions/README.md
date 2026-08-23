# Architecture decision records

Use ADRs for decisions that are expensive to reverse or affect public compatibility.

Name files as:

```text
NNNN-short-kebab-case-title.md
```

Each ADR should include status, context, decision, consequences, and alternatives considered. Accepted ADRs are immutable except for typo fixes; supersede them with a new ADR.

Accepted records:

- [0001: Deck Text as the system boundary](0001-deck-text-as-the-system-boundary.md)
- [0002: Resolve region proposals into physical card slots](0002-region-proposals-and-card-slots.md)
- [0003: Game8 userscript as an independent web adapter](0003-game8-userscript-as-independent-web-adapter.md)
- [0004: Distribute the userscript through GitHub Raw](0004-distribute-the-userscript-through-github-raw.md)
- [0005: Split the userscript release into pinned modules](0005-split-the-userscript-release-into-pinned-modules.md)
- [0006: Local React GUI as a presentation layer](0006-local-react-gui-as-presentation-layer.md)
- [0007: Generate QR only from a validated Deck](0007-generate-qr-only-from-validated-deck.md)
- [0008: Allow explicitly marked review draft QR codes](0008-review-draft-qr-codes.md)
