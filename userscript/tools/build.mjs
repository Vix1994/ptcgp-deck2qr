import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const PROJECT_DIRECTORY = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RELEASE_DIRECTORY = path.join(PROJECT_DIRECTORY, "release");
const CORE_FILENAME = "game8-ptcgp-deck-qr.core.js";
const CARD_MAP_FILENAME = "game8-ptcgp-deck-qr.card-map.json";
const USER_FILENAME = "game8-ptcgp-deck-qr.user.js";
const META_FILENAME = "game8-ptcgp-deck-qr.meta.js";
const REPOSITORY_URL = "https://github.com/Vix1994/ptcgp-deck2qr";
const RAW_REPOSITORY_URL =
  "https://raw.githubusercontent.com/Vix1994/ptcgp-deck2qr";

const packageJson = JSON.parse(
  await readFile(path.join(PROJECT_DIRECTORY, "package.json"), "utf8"),
);
const coreRelease = `v${packageJson.version}`;
const cardMapRelease = packageJson.cardMapRelease;
if (!/^v\d+\.\d+\.\d+$/.test(cardMapRelease)) {
  throw new Error("package.json cardMapRelease must be a v-prefixed semantic version");
}

function integrity(bytes) {
  return `sha256-${createHash("sha256").update(bytes).digest("base64")}`;
}

function taggedReleaseUrl(tag, filename) {
  return `${RAW_REPOSITORY_URL}/${tag}/userscript/release/${filename}`;
}

await mkdir(RELEASE_DIRECTORY, { recursive: true });
await copyFile(
  path.join(PROJECT_DIRECTORY, "generated/card-map.json"),
  path.join(RELEASE_DIRECTORY, CARD_MAP_FILENAME),
);
await build({
  entryPoints: [path.join(PROJECT_DIRECTORY, "src/index.js")],
  outfile: path.join(RELEASE_DIRECTORY, CORE_FILENAME),
  bundle: true,
  minify: true,
  sourcemap: false,
  legalComments: "eof",
  platform: "browser",
  format: "iife",
  globalName: "PTCGPGame8DeckQR",
  target: ["chrome109", "firefox115"],
  footer: { js: "globalThis.PTCGPGame8DeckQR = PTCGPGame8DeckQR;" },
  define: {
    __USERSCRIPT_VERSION__: JSON.stringify(packageJson.version),
  },
});

const coreBytes = await readFile(path.join(RELEASE_DIRECTORY, CORE_FILENAME));
const cardMapBytes = await readFile(path.join(RELEASE_DIRECTORY, CARD_MAP_FILENAME));
const taggedCoreUrl = taggedReleaseUrl(coreRelease, CORE_FILENAME);
const taggedCardMapUrl = taggedReleaseUrl(cardMapRelease, CARD_MAP_FILENAME);
const rawMainReleaseUrl = `${RAW_REPOSITORY_URL}/main/userscript/release`;
const metadata = `// ==UserScript==
// @name         PTCGP Game8 Deck QR
// @namespace    ${REPOSITORY_URL}
// @version      ${packageJson.version}
// @description  Generate Pokemon TCG Pocket deck-share QR codes beside Game8 deck lists.
// @homepageURL  ${REPOSITORY_URL}
// @supportURL   ${REPOSITORY_URL}/issues
// @updateURL    ${rawMainReleaseUrl}/${META_FILENAME}
// @downloadURL  ${rawMainReleaseUrl}/${USER_FILENAME}
// @require      ${taggedCoreUrl}#${integrity(coreBytes)}
// @resource     cardMap ${taggedCardMapUrl}#${integrity(cardMapBytes)}
// @match        https://game8.co/games/Pokemon-TCG-Pocket/archives/*
// @run-at       document-idle
// @grant        GM_getResourceText
// ==/UserScript==`;
const loader = `${metadata}

(() => {
  "use strict";
  const resourceText = GM_getResourceText("cardMap");
  if (typeof resourceText !== "string" || resourceText.length === 0) {
    throw new Error("PTCGP Game8 Deck QR could not load its card map resource");
  }
  const cardMap = JSON.parse(resourceText);
  const core = globalThis.PTCGPGame8DeckQR;
  if (typeof core?.start !== "function") {
    throw new Error("PTCGP Game8 Deck QR core module is unavailable");
  }
  core.start(cardMap);
})();
`;

await Promise.all([
  writeFile(path.join(RELEASE_DIRECTORY, META_FILENAME), `${metadata}\n`, "utf8"),
  writeFile(path.join(RELEASE_DIRECTORY, USER_FILENAME), loader, "utf8"),
]);

process.stdout.write(
  `Built loader ${Buffer.byteLength(loader)} B, core ${coreBytes.length} B, card map ${cardMapBytes.length} B\n`,
);
