import assert from "node:assert/strict";
import test from "node:test";

import { createDeckCode, parseDeckCode } from "ptcgp-deckcode";
import { deckCodeToDataURL } from "ptcgp-deckcode/qr";

import cardMap from "../generated/card-map.json" with { type: "json" };
import { deckBuilderNumbers, parseGame8DeckAlts } from "../src/game8-parser.js";

const HITMONCHAN_DECK_ALTS = [
  "Pokemon TCG Pocket- B1 122 Card Sandshrew ×2",
  "Pokemon TCG Pocket- B1 123 Card Sandslash ×2",
  "Pokemon TCG Pocket- B1 124 Card Hitmonchan ex ×1",
  "Pokemon TCG Pocket- B1 125 Card Sudowoodo ×1",
  "Pokemon TCG Pocket- B1 133 Card Archen ×2",
  "Pokemon TCG Pocket- B1 134 Card Archeops ×1",
  "Pokemon TCG Pocket- B1 143 Card Sandygast ×2",
  "Pokemon TCG Pocket- B1 144 Card Palossand ×2",
  "Pokemon TCG Pocket- B1 214 Card Plume Fossil ×2",
  "Pokemon TCG Pocket- P-A 002 Card X Speed ×1",
  "Pokemon TCG Pocket- P-A 005 Card Poke Ball ×2",
  "Pokemon TCG Pocket- P-A 007 Card Professor's Research ×2",
];

test("compact map records provenance and resolves every print in a real Game8 deck", () => {
  assert.equal(cardMap.schemaVersion, 1);
  assert.match(cardMap.source.sha256, /^[a-f0-9]{64}$/);
  assert.equal(Object.keys(cardMap.entries).length, cardMap.source.cardCount);

  const deck = parseGame8DeckAlts(HITMONCHAN_DECK_ALTS);
  const numbers = deckBuilderNumbers(deck.cards, cardMap.entries);
  assert.equal(numbers.length, 20);
});

test("creates a round-trippable deck-share code and PNG QR", async () => {
  const deck = parseGame8DeckAlts(HITMONCHAN_DECK_ALTS);
  const numbers = deckBuilderNumbers(deck.cards, cardMap.entries);
  const code = createDeckCode(numbers, ["fighting"]);
  const parsed = parseDeckCode(code);

  assert.equal(parsed.deckBuilderNrs.length, 20);
  assert.deepEqual(parsed.energies, ["fighting"]);

  const dataUrl = await deckCodeToDataURL(code, { width: 192, margin: 2 });
  assert.match(dataUrl, /^data:image\/png;base64,/);
});
