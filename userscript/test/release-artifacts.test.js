import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";

const PROJECT_DIRECTORY = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RELEASE_DIRECTORY = path.join(PROJECT_DIRECTORY, "release");
const CORE_FILENAME = "game8-ptcgp-deck-qr.core.js";
const CARD_MAP_FILENAME = "game8-ptcgp-deck-qr.card-map.json";
const USER_FILENAME = "game8-ptcgp-deck-qr.user.js";
const META_FILENAME = "game8-ptcgp-deck-qr.meta.js";

function integrity(bytes) {
  return `sha256-${createHash("sha256").update(bytes).digest("base64")}`;
}

function metadataValue(metadata, name) {
  const match = new RegExp(`^// @${name}\\s+(.+)$`, "m").exec(metadata);
  assert.ok(match, `missing @${name}`);
  return match[1].trim();
}

test("release loader pins modular artifacts with matching integrity hashes", async () => {
  const [packageText, loader, metadata, coreBytes, cardMapBytes] = await Promise.all([
    readFile(path.join(PROJECT_DIRECTORY, "package.json"), "utf8"),
    readFile(path.join(RELEASE_DIRECTORY, USER_FILENAME), "utf8"),
    readFile(path.join(RELEASE_DIRECTORY, META_FILENAME), "utf8"),
    readFile(path.join(RELEASE_DIRECTORY, CORE_FILENAME)),
    readFile(path.join(RELEASE_DIRECTORY, CARD_MAP_FILENAME)),
  ]);
  const packageJson = JSON.parse(packageText);
  const headerEnd = loader.indexOf("// ==/UserScript==") + "// ==/UserScript==".length;

  assert.equal(loader.slice(0, headerEnd), metadata.trimEnd());
  assert.equal(metadataValue(metadata, "version"), packageJson.version);
  assert.equal(metadataValue(metadata, "grant"), "GM_getResourceText");

  const requireValue = metadataValue(metadata, "require");
  assert.match(requireValue, new RegExp(`/v${packageJson.version}/.+/${CORE_FILENAME}#`));
  assert.equal(requireValue.split("#").at(-1), integrity(coreBytes));

  const resourceValue = metadataValue(metadata, "resource");
  assert.match(
    resourceValue,
    new RegExp(`^cardMap .+/${packageJson.cardMapRelease}/.+/${CARD_MAP_FILENAME}#`),
  );
  assert.equal(resourceValue.split("#").at(-1), integrity(cardMapBytes));

  assert.ok(Buffer.byteLength(loader) < 4_096, "loader should remain small");
  assert.ok(coreBytes.length < 60_000, "core should not contain the card map");
  assert.ok(cardMapBytes.length > coreBytes.length, "card map should remain a separate resource");
});

test("release loader passes the card-map resource to the core module", async () => {
  const [loader, cardMapText] = await Promise.all([
    readFile(path.join(RELEASE_DIRECTORY, USER_FILENAME), "utf8"),
    readFile(path.join(RELEASE_DIRECTORY, CARD_MAP_FILENAME), "utf8"),
  ]);
  let received;
  const context = {
    GM_getResourceText(name) {
      assert.equal(name, "cardMap");
      return cardMapText;
    },
    PTCGPGame8DeckQR: {
      start(cardMap) {
        received = cardMap;
      },
    },
  };

  runInNewContext(loader, context);

  assert.equal(received.source.cardCount, 3_761);
  assert.equal(Object.keys(received.entries).length, 3_761);
});

test("core artifact exposes an explicit start function", async () => {
  delete globalThis.PTCGPGame8DeckQR;
  const coreUrl = new URL(`../release/${CORE_FILENAME}?test=${Date.now()}`, import.meta.url);

  await import(coreUrl.href);

  assert.equal(typeof globalThis.PTCGPGame8DeckQR?.start, "function");
  delete globalThis.PTCGPGame8DeckQR;
});
