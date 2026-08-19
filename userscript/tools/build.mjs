import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const PROJECT_DIRECTORY = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(
  await readFile(path.join(PROJECT_DIRECTORY, "package.json"), "utf8"),
);
const REPOSITORY_URL = "https://github.com/Vix1994/ptcgp-deck2qr";
const RAW_RELEASE_URL =
  "https://raw.githubusercontent.com/Vix1994/ptcgp-deck2qr/main/userscript/release";

const metadata = `// ==UserScript==
// @name         PTCGP Game8 Deck QR
// @namespace    ${REPOSITORY_URL}
// @version      ${packageJson.version}
// @description  Generate Pokemon TCG Pocket deck-share QR codes beside Game8 deck lists.
// @homepageURL  ${REPOSITORY_URL}
// @supportURL   ${REPOSITORY_URL}/issues
// @updateURL    ${RAW_RELEASE_URL}/game8-ptcgp-deck-qr.meta.js
// @downloadURL  ${RAW_RELEASE_URL}/game8-ptcgp-deck-qr.user.js
// @match        https://game8.co/games/Pokemon-TCG-Pocket/archives/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==`;

await mkdir(path.join(PROJECT_DIRECTORY, "release"), { recursive: true });
await writeFile(
  path.join(PROJECT_DIRECTORY, "release/game8-ptcgp-deck-qr.meta.js"),
  `${metadata}\n`,
  "utf8",
);
await build({
  entryPoints: [path.join(PROJECT_DIRECTORY, "src/index.js")],
  outfile: path.join(PROJECT_DIRECTORY, "release/game8-ptcgp-deck-qr.user.js"),
  bundle: true,
  minify: true,
  sourcemap: false,
  legalComments: "none",
  platform: "browser",
  format: "iife",
  target: ["chrome109", "firefox115"],
  banner: { js: metadata },
  define: {
    __USERSCRIPT_VERSION__: JSON.stringify(packageJson.version),
  },
});
