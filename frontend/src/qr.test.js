import assert from 'node:assert/strict';
import test from 'node:test';

import {parseDeckCode} from 'ptcgp-deckcode';

import {generateDeckQr} from './qr.js';

test('generates a round-trippable deck code and PNG QR', async () => {
  const cards = [];
  for (let number = 1; number <= 5; number += 1) {
    cards.push({
      print_id: `A1-${String(number).padStart(3, '0')}`,
      image: `cPK_10_${String(number * 10).padStart(6, '0')}_00_TEST.webp`,
      count: 2,
    });
  }
  for (let number = 1; number <= 5; number += 1) {
    cards.push({
      print_id: `A1-${String(number + 5).padStart(3, '0')}`,
      image: `cTR_10_${String(number * 10).padStart(6, '0')}_00_TEST.webp`,
      count: 2,
    });
  }

  const result = await generateDeckQr({name: 'Test', energies: ['lightning'], cards});
  const parsed = parseDeckCode(result.deckCode);
  assert.equal(parsed.deckBuilderNrs.length, 20);
  assert.equal(parsed.pokemon.length, 10);
  assert.equal(parsed.trainers.length, 10);
  assert.deepEqual(parsed.energies, ['lightning']);
  assert.match(result.dataUrl, /^data:image\/png;base64,/);
});

test('fails closed for invalid totals and identities', async () => {
  await assert.rejects(
    generateDeckQr({
      name: 'Bad',
      energies: ['fire'],
      cards: [{print_id: 'A1-001', image: 'bad.webp', count: 2}],
    }),
    /缺少游戏实体编号/,
  );
});
