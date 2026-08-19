import assert from "node:assert/strict";
import test from "node:test";

import {
  deckBuilderNumbers,
  normalizeGame8Set,
  parseGame8CardAlt,
  parseGame8CardIdentity,
  parseGame8DeckAlts,
  parseGame8DeckCells,
} from "../src/game8-parser.js";

test("normalizes Game8 set aliases without destroying lowercase suffixes", () => {
  assert.equal(normalizeGame8Set("P-A"), "PROMO-A");
  assert.equal(normalizeGame8Set("a2b"), "A2b");
  assert.equal(normalizeGame8Set("B1a"), "B1a");
});

test("parses set, number, name, and count from a Game8 card alt", () => {
  assert.deepEqual(
    parseGame8CardAlt("Pokemon TCG Pocket- B1 122 Card Sandshrew ×2"),
    {
      set: "B1",
      number: 122,
      name: "Sandshrew",
      count: 2,
      printKey: "B1-122",
    },
  );
});

test("reads identity from img alt and quantity from its surrounding Game8 table cell", () => {
  assert.deepEqual(
    parseGame8CardIdentity("Pokemon TCG Pocket- B1a 001 Card Charmander"),
    {
      set: "B1a",
      number: 1,
      name: "Charmander",
      count: undefined,
      printKey: "B1a-001",
    },
  );

  const parsed = parseGame8DeckCells([
    {
      alts: [
        "Pokemon TCG Pocket- B1a 001 Card Charmander",
        "Magnifying Glass Icon",
      ],
      text: "Charmander ×2",
    },
  ]);
  assert.equal(parsed.totalCount, 2);
  assert.deepEqual(parsed.rejected, []);
  assert.equal(parsed.cards[0].printKey, "B1a-001");
  assert.equal(parsed.cards[0].count, 2);
});

test("rejects a recognized card identity when its adjacent quantity is missing", () => {
  const parsed = parseGame8DeckCells([
    {
      alts: ["Pokemon TCG Pocket- B1a 001 Card Charmander"],
      text: "Charmander",
    },
  ]);
  assert.equal(parsed.totalCount, 0);
  assert.equal(parsed.rejected.length, 1);
});

test("parses a complete 20-card Game8 deck and ignores unrelated images", () => {
  const alts = [
    "Pokemon TCG Pocket - Hitmonchan ex Deck (Mega Rising)",
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

  const parsed = parseGame8DeckAlts(alts);
  assert.equal(parsed.cards.length, 12);
  assert.equal(parsed.totalCount, 20);
  assert.deepEqual(parsed.rejected, []);
  assert.equal(parsed.cards.find((card) => card.name === "Poke Ball")?.printKey, "PROMO-A-005");

  const splitCells = alts.slice(1).map((alt) => {
    const match = /^(.*?\sCard\s+)(.+?)\s+([×xX]\s*[12])$/.exec(alt);
    assert.ok(match);
    return {
      alts: [`${match[1]}${match[2]}`],
      text: `${match[2]} ${match[3]}`,
    };
  });
  const splitParsed = parseGame8DeckCells(splitCells);
  assert.equal(splitParsed.cards.length, 12);
  assert.equal(splitParsed.totalCount, 20);
  assert.deepEqual(splitParsed.rejected, []);
});

test("fails closed when a print does not resolve or the total is not twenty", () => {
  assert.throws(
    () =>
      deckBuilderNumbers(
        [{ printKey: "B1-122", name: "Sandshrew", count: 2 }],
        { "B1-122": 122 },
      ),
    /总数必须是 20/,
  );
  assert.throws(
    () =>
      deckBuilderNumbers(
        [{ printKey: "B1-999", name: "Missing", count: 2 }],
        {},
      ),
    /索引中找不到/,
  );
});
