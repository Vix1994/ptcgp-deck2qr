import test from 'node:test';
import assert from 'node:assert/strict';

import {errorLabel, initialLanguage, styleLabel, translate} from './i18n.js';

test('selects and persists supported interface languages', () => {
  assert.equal(initialLanguage('en', 'zh-CN'), 'en');
  assert.equal(initialLanguage(null, 'zh-TW'), 'zh');
  assert.equal(initialLanguage(null, 'fr-FR'), 'en');
});

test('translates interface, style, and recognition error copy', () => {
  assert.equal(translate('zh', 'setup.start'), '开始识别');
  assert.equal(translate('en', 'setup.start'), 'Start recognition');
  assert.equal(translate('en', 'results.entries', {count: 7}), '7 card entries');
  assert.equal(
    translate('zh', 'result.draftQrReady', {count: 2}),
    '草稿二维码已生成，导入后请检查 2 张候选卡',
  );
  assert.equal(styleLabel('en', 'count-badge'), 'Number badges');
  assert.equal(errorLabel('en', 'count-ambiguous'), 'One or more card counts are uncertain');
});
