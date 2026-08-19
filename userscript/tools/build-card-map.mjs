import { createHash } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_OUTPUT = path.resolve(SCRIPT_DIRECTORY, "../generated/card-map.json");
const IMAGE_PATTERN = /^(cPK|cTR)_\d+_(\d{6})_/;
const TRAINER_OFFSET = 1_000_000;

function readOption(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

async function resolveCardsPath(databasePath) {
  const info = await stat(databasePath);
  return info.isDirectory() ? path.join(databasePath, "cards.json") : databasePath;
}

function deckBuilderNumber(image) {
  const match = IMAGE_PATTERN.exec(image);
  if (!match) {
    throw new Error(`Unsupported card image identity: ${image}`);
  }

  const encodedEntity = Number.parseInt(match[2], 10);
  if (encodedEntity % 10 !== 0) {
    throw new Error(`Card image identity is not divisible by ten: ${image}`);
  }

  const entity = encodedEntity / 10;
  return match[1] === "cTR" ? TRAINER_OFFSET + entity : entity;
}

function compareAscii(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function buildIndex(cards) {
  const pairs = [];
  const seen = new Set();

  for (const card of cards) {
    if (
      typeof card !== "object" ||
      card === null ||
      typeof card.set !== "string" ||
      !Number.isInteger(card.number) ||
      card.number <= 0 ||
      typeof card.image !== "string"
    ) {
      throw new Error("cards.json contains a card with an unsupported schema");
    }

    const key = `${card.set}-${String(card.number).padStart(3, "0")}`;
    if (seen.has(key)) {
      throw new Error(`Duplicate print identity in cards.json: ${key}`);
    }
    seen.add(key);
    pairs.push([key, deckBuilderNumber(card.image)]);
  }

  pairs.sort(([left], [right]) => compareAscii(left, right));
  return Object.fromEntries(pairs);
}

async function main() {
  const databasePath = readOption("--database-path") ?? process.env.PTCGP_DATABASE_PATH;
  if (!databasePath) {
    throw new Error(
      "Pass --database-path <dist-or-cards.json> or set PTCGP_DATABASE_PATH to rebuild the card map.",
    );
  }

  const cardsPath = await resolveCardsPath(path.resolve(databasePath));
  const sourceBytes = await readFile(cardsPath);
  const parsed = JSON.parse(sourceBytes.toString("utf8"));
  const cards = Array.isArray(parsed) ? parsed : parsed.cards;
  if (!Array.isArray(cards)) {
    throw new Error("cards.json must contain an array or an object with a cards array");
  }

  const entries = buildIndex(cards);
  const output = {
    schemaVersion: 1,
    algorithmVersion: "deck-builder-number-v1",
    source: {
      file: "cards.json",
      sha256: createHash("sha256").update(sourceBytes).digest("hex"),
      cardCount: cards.length,
    },
    entries,
  };

  const outputPath = path.resolve(readOption("--output") ?? DEFAULT_OUTPUT);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`Wrote ${Object.keys(entries).length} print mappings to ${outputPath}\n`);
}

await main();
