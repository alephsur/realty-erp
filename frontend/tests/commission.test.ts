import assert from 'node:assert/strict';
import { test } from 'vitest';
import { previewCommission, formatCents } from '../src/lib/commission.ts';

test('rounds half cents up and preserves the full split', () => {
  assert.deepEqual(previewCommission('100.50', '1', '50'), { total: 101n, agent: 51n, agency: 50n });
  assert.equal(formatCents(101n), '1,01 €');
});

test('calculates a residential sale and accepts explicit zero rates', () => {
  assert.deepEqual(previewCommission('200000.01', '3', '40'), { total: 600000n, agent: 240000n, agency: 360000n });
  assert.deepEqual(previewCommission('100', '0', '0'), { total: 0n, agent: 0n, agency: 0n });
});

test('rejects missing, negative, non-finite and overprecise inputs', () => {
  for (const price of ['', '0', '-1', 'NaN', 'Infinity', '1.001', '100000000000000']) {
    assert.equal(previewCommission(price, '3', '40'), null);
  }
  for (const rate of ['', '-1', '101', 'NaN', '0.00001']) {
    assert.equal(previewCommission('100', rate, '40'), null);
    assert.equal(previewCommission('100', '3', rate), null);
  }
});
