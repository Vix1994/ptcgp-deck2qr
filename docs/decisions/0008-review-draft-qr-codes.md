# ADR 0008: Allow explicitly marked review draft QR codes

Status: Accepted

Supersedes: the partial-deck QR prohibition in ADR 0007. Its dependency boundaries and validated
20-card path remain in force.

## Context

Recognition can have enough structural evidence to identify 18 or 19 cards, or enough visual
evidence to select a top candidate for every slot while retaining entity ambiguity. Refusing all QR
output in those cases prevents a user from trying an import and correcting the result in the game.

The pinned Deck Code encoder can serialize fewer than 20 identities, but acceptance of an incomplete
code by the game scanner has not yet been verified. A review aid must therefore remain distinct from
a successfully recognized deck.

## Decision

- Keep canonical Deck validation, `accepted=true`, and formal `deck.txt` output restricted to exactly
  20 reliable cards.
- Permit a separate review draft only when it contains 18 to 20 cards, every detected slot has direct
  image evidence, every count is reliably 1 or 2, every slot has a selected database candidate, and
  there are no detection or structural errors.
- Allow top-1 candidates in the review draft when entity confidence is insufficient. Preserve those
  cards as uncertain in diagnostics and the GUI.
- Require an explicit `allow_incomplete` marker at both the Python QR adapter and browser encoder
  boundaries before encoding 18 or 19 cards. The normal QR path continues to reject totals other
  than 20.
- Label the result as an incomplete draft, report the missing and uncertain-card counts, and warn that
  scanner acceptance is unverified. Write only `deck.partial.txt`, never formal `deck.txt`.
- Do not generate a review draft below 18 cards or when count, slot, mapping, or detection evidence is
  unreliable.

## Consequences

- Users can try importing an almost complete recognition and edit it instead of receiving no QR.
- Draft availability never changes recognition acceptance or canonical Deck Text validity.
- An incomplete QR may be rejected by the game; the GUI communicates this uncertainty explicitly.
- The QR protocol remains isolated from screenshots and recognition internals because it still
  consumes only a Deck model plus the active card database.

## Alternatives considered

- **Require exactly 20 cards for every QR:** rejected because it prevents a useful, clearly labeled
  recovery path for one or two missing cards.
- **Treat 18 or 19 cards as successful recognition:** rejected because it would violate the game-deck
  and Deck Text invariants.
- **Allow any partial total:** rejected because heavily incomplete recognition is less useful and has
  substantially higher risk of presenting misleading output.
