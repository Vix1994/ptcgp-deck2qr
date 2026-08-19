const CARD_ALT_WITH_COUNT_PATTERN =
  /^Pokemon TCG Pocket\s*-\s*(\S+)\s+(\d+)\s+Card\s+(.+?)\s*[×xX]\s*([12])\s*$/i;
const CARD_IDENTITY_ALT_PATTERN =
  /^Pokemon TCG Pocket\s*-\s*(\S+)\s+(\d+)\s+Card\s+(.+?)\s*$/i;
const COUNT_TEXT_PATTERN = /[×xX]\s*([12])\s*$/;

const SET_PATTERN = /^([AB]\d+)([a-z]?)$/i;

export function normalizeGame8Set(value) {
  const trimmed = value.trim();
  if (/^(?:P-A|PROMO-A)$/i.test(trimmed)) {
    return "PROMO-A";
  }

  const match = SET_PATTERN.exec(trimmed);
  if (!match) {
    throw new Error(`无法识别 Game8 系列编号：${value}`);
  }
  return `${match[1].toUpperCase()}${match[2].toLowerCase()}`;
}

export function printKey(set, number) {
  return `${set}-${String(number).padStart(3, "0")}`;
}

export function parseGame8CardIdentity(alt) {
  const trimmed = alt.trim();
  const match = CARD_ALT_WITH_COUNT_PATTERN.exec(trimmed) ?? CARD_IDENTITY_ALT_PATTERN.exec(trimmed);
  if (!match) {
    return null;
  }

  const set = normalizeGame8Set(match[1]);
  const number = Number.parseInt(match[2], 10);
  return {
    set,
    number,
    name: match[3].trim(),
    count: match[4] ? Number.parseInt(match[4], 10) : undefined,
    printKey: printKey(set, number),
  };
}

export function parseGame8CardAlt(alt) {
  const card = parseGame8CardIdentity(alt);
  return card?.count ? card : null;
}

function aggregateCards(evidence) {
  const cardsByPrint = new Map();
  const rejected = [];

  for (const item of evidence) {
    const identity = parseGame8CardIdentity(item.alt);
    if (!identity) {
      continue;
    }

    const countMatch = COUNT_TEXT_PATTERN.exec(item.text.trim());
    const count = identity.count ?? (countMatch ? Number.parseInt(countMatch[1], 10) : undefined);
    if (!count) {
      rejected.push(`${item.alt} | ${item.text}`);
      continue;
    }
    const card = { ...identity, count };

    const existing = cardsByPrint.get(card.printKey);
    if (existing) {
      const combinedCount = existing.count + card.count;
      if (combinedCount > 2) {
        throw new Error(`同一张卡的数量超过 2：${card.printKey}`);
      }
      existing.count = combinedCount;
    } else {
      cardsByPrint.set(card.printKey, { ...card });
    }
  }

  const cards = [...cardsByPrint.values()].sort((left, right) => {
    const setOrder = left.set.localeCompare(right.set, "en");
    return setOrder === 0 ? left.number - right.number : setOrder;
  });
  const totalCount = cards.reduce((total, card) => total + card.count, 0);
  return { cards, rejected, totalCount };
}

export function parseGame8DeckAlts(alts) {
  return aggregateCards(alts.map((alt) => ({ alt, text: alt })));
}

export function parseGame8DeckCells(cells) {
  const evidence = [];
  for (const cell of cells) {
    const matchingAlt = cell.alts.find((alt) => parseGame8CardIdentity(alt));
    if (matchingAlt) {
      evidence.push({ alt: matchingAlt, text: cell.text });
    }
  }
  return aggregateCards(evidence);
}

export function deckBuilderNumbers(cards, cardMap) {
  const result = [];
  const entityCounts = new Map();

  for (const card of cards) {
    const number = cardMap[card.printKey];
    if (!Number.isInteger(number)) {
      throw new Error(`精简卡牌索引中找不到：${card.printKey} ${card.name}`);
    }

    const combinedCount = (entityCounts.get(number) ?? 0) + card.count;
    if (combinedCount > 2) {
      throw new Error(`同一游戏实体的数量超过 2：${card.name}`);
    }
    entityCounts.set(number, combinedCount);

    for (let copy = 0; copy < card.count; copy += 1) {
      result.push(number);
    }
  }

  if (result.length !== 20) {
    throw new Error(`卡组总数必须是 20，当前解析到 ${result.length}`);
  }
  return result;
}
