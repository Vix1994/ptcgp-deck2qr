import {createDeckCode, deckBuilderNrFromImage} from 'ptcgp-deckcode';
import {deckCodeToDataURL} from 'ptcgp-deckcode/qr';

export async function generateDeckQr(input) {
  if (!input || !Array.isArray(input.cards) || !Array.isArray(input.energies)) {
    throw new Error('二维码输入格式无效');
  }

  const deckBuilderNumbers = [];
  const entityCounts = new Map();
  for (const card of input.cards) {
    const number = deckBuilderNrFromImage(card.image);
    if (!Number.isInteger(number)) {
      throw new Error(`无法生成二维码：${card.print_id} 缺少游戏实体编号`);
    }
    if (!Number.isInteger(card.count) || card.count < 1 || card.count > 2) {
      throw new Error(`无法生成二维码：${card.print_id} 数量无效`);
    }
    const combined = (entityCounts.get(number) || 0) + card.count;
    if (combined > 2) {
      throw new Error(`无法生成二维码：${card.print_id} 对应实体超过 2 张`);
    }
    entityCounts.set(number, combined);
    for (let copy = 0; copy < card.count; copy += 1) deckBuilderNumbers.push(number);
  }
  if (deckBuilderNumbers.length !== 20) {
    throw new Error(`无法生成二维码：卡组总数为 ${deckBuilderNumbers.length}，应为 20`);
  }

  const deckCode = createDeckCode(deckBuilderNumbers, input.energies);
  const dataUrl = await deckCodeToDataURL(deckCode, {
    width: 360,
    margin: 2,
    errorCorrectionLevel: 'M',
  });
  return {deckCode, dataUrl};
}
