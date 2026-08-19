import { createDeckCode } from "ptcgp-deckcode";
import { deckCodeToDataURL } from "ptcgp-deckcode/qr";
import cardMap from "../generated/card-map.json";
import {
  deckBuilderNumbers,
  parseGame8DeckAlts,
  parseGame8DeckCells,
} from "./game8-parser.js";

const DECK_HEADING_PATTERN = /\bDeck Card List\s*$/i;
const HEADING_SELECTOR = "h2,h3,h4,h5,h6";
const ENERGY_DEFINITIONS = [
  ["grass", "草", "Grass"],
  ["fire", "火", "Fire"],
  ["water", "水", "Water"],
  ["lightning", "雷", "Lightning"],
  ["psychic", "超", "Psychic"],
  ["fighting", "斗", "Fighting"],
  ["darkness", "恶", "Darkness"],
  ["metal", "钢", "Metal"],
];
const ENERGY_BY_LABEL = new Map(
  ENERGY_DEFINITIONS.flatMap(([value, , label]) => [
    [label.toLowerCase(), value],
    ...(value === "lightning" ? [["electric", value]] : []),
  ]),
);

let activeDialog;
let mutationTimer;

function headingRank(heading) {
  return Number.parseInt(heading.tagName.slice(1), 10);
}

function isBefore(left, right) {
  return Boolean(left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING);
}

function isBetween(start, element, end) {
  return isBefore(start, element) && (!end || isBefore(element, end));
}

function deckHeadings() {
  return [...document.querySelectorAll(HEADING_SELECTOR)].filter((heading) =>
    DECK_HEADING_PATTERN.test(heading.textContent?.trim() ?? ""),
  );
}

function imageAltsWithin(element) {
  return [...element.querySelectorAll("img[alt]")].map((image) => image.getAttribute("alt") ?? "");
}

function cardCellsWithin(table) {
  return [...table.querySelectorAll("td")].map((cell) => ({
    alts: imageAltsWithin(cell),
    text: cell.textContent ?? "",
  }));
}

function extractDeckForHeading(heading) {
  const headings = deckHeadings();
  const headingIndex = headings.indexOf(heading);
  const nextHeading = headingIndex === -1 ? undefined : headings[headingIndex + 1];
  const candidates = [...document.querySelectorAll("table")]
    .filter((table) => isBetween(heading, table, nextHeading))
    .map((table) => parseGame8DeckCells(cardCellsWithin(table)))
    .filter((candidate) => candidate.cards.length > 0);

  const exactCandidate = candidates.find(
    (candidate) => candidate.totalCount === 20 && candidate.rejected.length === 0,
  );
  if (exactCandidate) {
    return exactCandidate;
  }

  const fallbackAlts = [...document.querySelectorAll("img[alt]")]
    .filter((image) => isBetween(heading, image, nextHeading))
    .map((image) => image.getAttribute("alt") ?? "");
  const fallback = parseGame8DeckAlts(fallbackAlts);
  const best = candidates.sort((left, right) => right.totalCount - left.totalCount)[0] ?? fallback;

  if (best.rejected.length > 0) {
    throw new Error(`有 ${best.rejected.length} 张卡的 Game8 文本格式无法识别`);
  }
  if (best.totalCount !== 20) {
    throw new Error(`没有找到完整的 20 张卡；当前区块解析到 ${best.totalCount} 张`);
  }
  return best;
}

function precedingSectionHeading(heading) {
  const rank = headingRank(heading);
  return [...document.querySelectorAll(HEADING_SELECTOR)]
    .filter((candidate) => headingRank(candidate) < rank && isBefore(candidate, heading))
    .at(-1);
}

function detectEnergy(heading) {
  const sectionHeading = precedingSectionHeading(heading);
  if (!sectionHeading) {
    return undefined;
  }

  const candidates = [...document.querySelectorAll("td,th,p,span,div")].filter((element) =>
    isBetween(sectionHeading, element, heading),
  );
  for (const element of candidates) {
    const match = /^\s*(Grass|Fire|Water|Lightning|Electric|Psychic|Fighting|Darkness|Metal)\s+Deck\s*$/i.exec(
      element.textContent ?? "",
    );
    if (match) {
      return ENERGY_BY_LABEL.get(match[1].toLowerCase());
    }
  }
  return undefined;
}

function deckName(heading) {
  return (heading.textContent ?? "PTCGP Deck").replace(/\s*Card List\s*$/i, "").trim();
}

function sanitizeFilename(value) {
  const sanitized = value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-").replace(/\s+/g, " ").trim();
  return sanitized || "ptcgp-deck";
}

function createActionButton(heading) {
  const host = document.createElement("span");
  host.dataset.ptcgpDeckQrAction = "";
  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      :host { display: inline-flex; margin-inline-start: 10px; vertical-align: middle; }
      button {
        appearance: none;
        border: 1px solid #1769aa;
        border-radius: 7px;
        background: #fff;
        color: #12578d;
        cursor: pointer;
        font: 700 12px/1.2 inherit;
        letter-spacing: .01em;
        padding: 6px 10px;
        transition: background-color 140ms ease, color 140ms ease, transform 140ms ease;
      }
      button:hover { background: #1769aa; color: #fff; }
      button:active { transform: translateY(1px); }
      button:focus-visible { outline: 3px solid rgba(23, 105, 170, .28); outline-offset: 2px; }
      button:disabled { cursor: wait; opacity: .62; }
      @media (prefers-reduced-motion: reduce) { button { transition: none; } }
    </style>
    <button type="button">生成 QR</button>
  `;
  const button = shadow.querySelector("button");
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    button.disabled = true;
    button.textContent = "解析中…";
    try {
      const deck = extractDeckForHeading(heading);
      const numbers = deckBuilderNumbers(deck.cards, cardMap.entries);
      showDialog({
        name: deckName(heading),
        deck,
        numbers,
        detectedEnergy: detectEnergy(heading),
        trigger: button,
      });
    } catch (error) {
      showDialog({ name: deckName(heading), error, trigger: button });
    } finally {
      button.disabled = false;
      button.textContent = "生成 QR";
    }
  });
  heading.append(host);
}

function injectButtons() {
  for (const heading of deckHeadings()) {
    if (!heading.querySelector(":scope > [data-ptcgp-deck-qr-action]")) {
      createActionButton(heading);
    }
  }
}

function createDialog() {
  const host = document.createElement("div");
  host.dataset.ptcgpDeckQrDialog = "";
  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      :host {
        --blue: #1769aa;
        --blue-deep: #12578d;
        --ink: #20252b;
        --muted: #66717c;
        --line: #dce2e8;
        --surface: #ffffff;
        --soft: #f4f7f9;
        --good: #18794e;
        --bad: #b42318;
        color: var(--ink);
        font-family: inherit;
      }
      [hidden] { display: none !important; }
      .overlay {
        align-items: center;
        background: rgba(18, 25, 32, .58);
        box-sizing: border-box;
        display: flex;
        inset: 0;
        justify-content: center;
        padding: 20px;
        position: fixed;
        z-index: 2147483647;
        animation: overlay-in 140ms ease-out;
      }
      .panel {
        background: var(--surface);
        border: 1px solid rgba(255,255,255,.65);
        border-radius: 14px;
        box-shadow: 0 18px 54px rgba(0,0,0,.25);
        box-sizing: border-box;
        max-height: min(760px, calc(100vh - 40px));
        overflow: auto;
        padding: 18px;
        position: relative;
        width: min(430px, 100%);
        animation: panel-in 160ms ease-out;
      }
      .close {
        align-items: center;
        appearance: none;
        background: transparent;
        border: 0;
        border-radius: 7px;
        color: var(--muted);
        cursor: pointer;
        display: flex;
        font: 500 24px/1 inherit;
        height: 36px;
        justify-content: center;
        position: absolute;
        right: 14px;
        top: 14px;
        width: 36px;
      }
      .close:hover { background: var(--soft); color: var(--ink); }
      .close:focus-visible, button:focus-visible { outline: 3px solid rgba(23,105,170,.28); outline-offset: 2px; }
      .eyebrow { color: var(--blue-deep); font-size: 11px; font-weight: 800; letter-spacing: .1em; margin: 0 42px 7px 0; text-transform: uppercase; }
      h2 { color: var(--ink); font-size: 21px; line-height: 1.28; margin: 0 42px 8px 0; text-wrap: pretty; }
      .summary { align-items: center; display: flex; gap: 8px; margin-bottom: 12px; }
      .status-chip { background: #e9f6ef; border-radius: 999px; color: var(--good); font-size: 12px; font-weight: 800; padding: 5px 9px; }
      .source { color: var(--muted); font-size: 12px; }
      .section-label { color: var(--ink); display: block; font-size: 13px; font-weight: 800; margin-bottom: 8px; }
      .energy-grid { display: grid; gap: 7px; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 10px; }
      .energy {
        appearance: none;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        color: var(--ink);
        cursor: pointer;
        font: 700 12px/1.15 inherit;
        min-height: 42px;
        padding: 7px 4px;
        transition: border-color 140ms ease, background-color 140ms ease, color 140ms ease;
      }
      .energy:hover { border-color: var(--blue); }
      .energy[aria-pressed="true"] { background: var(--blue); border-color: var(--blue); color: #fff; }
      .hint { color: var(--muted); font-size: 12px; line-height: 1.45; margin: 0 0 10px; }
      .qr-shell { align-items: center; background: var(--soft); border: 1px solid var(--line); border-radius: 12px; display: flex; justify-content: center; min-height: 252px; padding: 10px; }
      .qr-shell img { background: #fff; border-radius: 8px; display: block; height: auto; max-width: 228px; width: 100%; }
      .qr-placeholder { color: var(--muted); font-size: 13px; max-width: 260px; text-align: center; text-wrap: pretty; }
      .message { color: var(--muted); font-size: 12px; line-height: 1.45; margin: 10px 0 0; min-height: 18px; text-align: center; }
      .message[data-tone="error"] { color: var(--bad); }
      .message[data-tone="good"] { color: var(--good); }
      .actions { display: grid; gap: 8px; grid-template-columns: 1fr 1fr; margin-top: 10px; }
      .action {
        appearance: none;
        border: 1px solid var(--line);
        border-radius: 9px;
        cursor: pointer;
        font: 800 13px/1 inherit;
        min-height: 42px;
        padding: 10px 12px;
      }
      .action.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
      .action.primary:hover { background: var(--blue-deep); }
      .action.secondary { background: var(--surface); color: var(--ink); }
      .action.secondary:hover { background: var(--soft); }
      .action:disabled { cursor: not-allowed; opacity: .46; }
      .error-box { background: #fff2f0; border: 1px solid #ffd2cc; border-radius: 10px; color: var(--bad); font-size: 13px; line-height: 1.5; padding: 13px; }
      @keyframes overlay-in { from { opacity: 0; } }
      @keyframes panel-in { from { opacity: 0; transform: translateY(8px) scale(.985); } }
      @media (max-width: 480px) {
        .overlay { align-items: flex-end; padding: 10px; }
        .panel { border-radius: 14px 14px 10px 10px; max-height: calc(100vh - 20px); padding: 18px 16px; }
        .energy-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (prefers-reduced-motion: reduce) {
        .overlay, .panel { animation: none; }
        .energy { transition: none; }
      }
    </style>
    <div class="overlay" hidden>
      <section class="panel" role="dialog" aria-modal="true" aria-labelledby="ptcgp-qr-title">
        <button class="close" type="button" aria-label="关闭">×</button>
        <p class="eyebrow">PTCGP Deck Share</p>
        <h2 id="ptcgp-qr-title"></h2>
        <div class="content"></div>
      </section>
    </div>
  `;
  document.body.append(host);

  const overlay = shadow.querySelector(".overlay");
  const closeButton = shadow.querySelector(".close");
  const content = shadow.querySelector(".content");
  const title = shadow.querySelector("h2");
  const state = {
    host,
    shadow,
    overlay,
    content,
    title,
    trigger: undefined,
    name: "",
    numbers: [],
    selectedEnergies: new Set(),
    deckCode: undefined,
    qrDataUrl: undefined,
    generation: 0,
  };

  function close() {
    overlay.hidden = true;
    document.removeEventListener("keydown", onKeydown, true);
    state.trigger?.focus();
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  }

  closeButton.addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });
  state.close = close;
  state.onKeydown = onKeydown;
  return state;
}

function renderError(dialog, error) {
  dialog.content.replaceChildren();
  const errorBox = document.createElement("div");
  errorBox.className = "error-box";
  errorBox.textContent = error instanceof Error ? error.message : String(error);
  dialog.content.append(errorBox);
}

function energyValues(dialog) {
  return ENERGY_DEFINITIONS.map(([value]) => value).filter((value) =>
    dialog.selectedEnergies.has(value),
  );
}

async function generateQr(dialog) {
  const generation = ++dialog.generation;
  const energies = energyValues(dialog);
  const message = dialog.shadow.querySelector(".message");
  const image = dialog.shadow.querySelector(".qr-image");
  const placeholder = dialog.shadow.querySelector(".qr-placeholder");
  const downloadButton = dialog.shadow.querySelector("[data-action='download']");
  const copyButton = dialog.shadow.querySelector("[data-action='copy']");

  dialog.deckCode = undefined;
  dialog.qrDataUrl = undefined;
  image.hidden = true;
  downloadButton.disabled = true;
  copyButton.disabled = true;

  if (energies.length === 0) {
    placeholder.hidden = false;
    placeholder.textContent = "请选择 1–3 种能量后生成二维码。";
    message.textContent = "";
    return;
  }

  placeholder.hidden = false;
  placeholder.textContent = "正在生成二维码…";
  message.dataset.tone = "";
  message.textContent = "";
  try {
    const code = createDeckCode(dialog.numbers, energies);
    const dataUrl = await deckCodeToDataURL(code, {
      width: 320,
      margin: 2,
      errorCorrectionLevel: "M",
    });
    if (generation !== dialog.generation) {
      return;
    }
    dialog.deckCode = code;
    dialog.qrDataUrl = dataUrl;
    image.src = dataUrl;
    image.alt = `${dialog.name} 的 PTCGP 卡组二维码`;
    image.hidden = false;
    placeholder.hidden = true;
    downloadButton.disabled = false;
    copyButton.disabled = false;
    message.dataset.tone = "good";
    message.textContent = `已生成 ${energies.length} 种能量的卡组二维码`;
  } catch (error) {
    if (generation !== dialog.generation) {
      return;
    }
    placeholder.hidden = false;
    placeholder.textContent = "二维码生成失败。";
    message.dataset.tone = "error";
    message.textContent = error instanceof Error ? error.message : String(error);
  }
}

function renderDeck(dialog, deck, detectedEnergy) {
  dialog.content.innerHTML = `
    <div class="summary">
      <span class="status-chip">${deck.totalCount}/20 已校验</span>
      <span class="source">${deck.cards.length} 种卡牌</span>
    </div>
    <span class="section-label">确认能量</span>
    <div class="energy-grid"></div>
    <p class="hint">已根据 Game8 当前卡组区块预选；可手动调整，最多选择三种。</p>
    <div class="qr-shell">
      <img class="qr-image" hidden>
      <span class="qr-placeholder">请选择 1–3 种能量后生成二维码。</span>
    </div>
    <p class="message" aria-live="polite"></p>
    <div class="actions">
      <button class="action primary" data-action="download" type="button" disabled>下载 PNG</button>
      <button class="action secondary" data-action="copy" type="button" disabled>复制 Deck Code</button>
    </div>
  `;

  const grid = dialog.shadow.querySelector(".energy-grid");
  for (const [value, shortLabel, englishLabel] of ENERGY_DEFINITIONS) {
    const button = document.createElement("button");
    button.className = "energy";
    button.type = "button";
    button.dataset.energy = value;
    button.setAttribute("aria-pressed", String(dialog.selectedEnergies.has(value)));
    button.textContent = `${shortLabel} ${englishLabel}`;
    button.addEventListener("click", () => {
      if (dialog.selectedEnergies.has(value)) {
        dialog.selectedEnergies.delete(value);
      } else if (dialog.selectedEnergies.size < 3) {
        dialog.selectedEnergies.add(value);
      } else {
        const message = dialog.shadow.querySelector(".message");
        message.dataset.tone = "error";
        message.textContent = "最多只能选择三种能量。";
        return;
      }
      for (const energyButton of grid.querySelectorAll(".energy")) {
        energyButton.setAttribute(
          "aria-pressed",
          String(dialog.selectedEnergies.has(energyButton.dataset.energy)),
        );
      }
      void generateQr(dialog);
    });
    grid.append(button);
  }

  dialog.shadow.querySelector("[data-action='download']").addEventListener("click", () => {
    if (!dialog.qrDataUrl) {
      return;
    }
    const link = document.createElement("a");
    link.href = dialog.qrDataUrl;
    link.download = `${sanitizeFilename(dialog.name)}-qr.png`;
    link.click();
  });

  dialog.shadow.querySelector("[data-action='copy']").addEventListener("click", async () => {
    if (!dialog.deckCode) {
      return;
    }
    const message = dialog.shadow.querySelector(".message");
    try {
      await navigator.clipboard.writeText(dialog.deckCode);
      message.dataset.tone = "good";
      message.textContent = "Deck Code 已复制。";
    } catch {
      message.dataset.tone = "error";
      message.textContent = "浏览器拒绝访问剪贴板，请手动复制。";
    }
  });

  if (detectedEnergy) {
    dialog.selectedEnergies.add(detectedEnergy);
    const selectedButton = grid.querySelector(`[data-energy="${detectedEnergy}"]`);
    selectedButton?.setAttribute("aria-pressed", "true");
  }
  void generateQr(dialog);
}

function showDialog({ name, deck, numbers, detectedEnergy, error, trigger }) {
  activeDialog ??= createDialog();
  activeDialog.name = name;
  activeDialog.title.textContent = name;
  activeDialog.trigger = trigger;
  activeDialog.numbers = numbers ?? [];
  activeDialog.selectedEnergies = new Set();
  activeDialog.deckCode = undefined;
  activeDialog.qrDataUrl = undefined;
  activeDialog.generation += 1;

  if (error) {
    renderError(activeDialog, error);
  } else {
    renderDeck(activeDialog, deck, detectedEnergy);
  }

  activeDialog.overlay.hidden = false;
  document.addEventListener("keydown", activeDialog.onKeydown, true);
  activeDialog.shadow.querySelector(".close").focus();
}

injectButtons();
new MutationObserver(() => {
  window.clearTimeout(mutationTimer);
  mutationTimer = window.setTimeout(injectButtons, 120);
}).observe(document.body, { childList: true, subtree: true });

console.info(
  `[PTCGP Game8 Deck QR] v${__USERSCRIPT_VERSION__}; card map ${cardMap.source.sha256.slice(0, 12)}`,
);
