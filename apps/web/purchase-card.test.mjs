import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { purchaseCard, purchaseDetail, money, priceBars } from './purchase-card.js';
import { filterExamples } from './purchase-repository.js';

const data = JSON.parse(readFileSync(new URL('./assets/purchase-examples.json', import.meta.url), 'utf8'));
for (const [index, analysis] of data.items.entries()) {
  const original = JSON.parse(readFileSync(new URL(`../../tests/fixtures/contracts-v1/${data.fixture_files[index]}`, import.meta.url), 'utf8'));
  assert.deepEqual(analysis, original, 'Preview must preserve registered fixture values');
  const markup = purchaseCard(analysis, index);
  assert.ok(markup.includes(analysis.target.agency_name));
  if (analysis.difference === null) {
    assert.ok(!markup.includes('+0원'), 'Missing comparisons must not become zero');
    assert.ok(purchaseDetail(analysis).includes('계산하지 않았습니다'));
  }
}
const analysis = data.items[0];
assert.ok(purchaseCard(analysis, 0).includes('+30,000원'));
assert.ok(purchaseCard(analysis, 0).includes('+25%'));
assert.ok(purchaseDetail(analysis).includes('+30,000원'));
assert.ok(priceBars(analysis).includes('width:100%'));
assert.ok(priceBars(analysis).includes('width:80%'), 'Bars must share the same zero baseline');
assert.equal(money(null), '확인 불가');
assert.equal(money('0'), '0원');
assert.equal(money('-30000', true), '-30,000원');
const unsafe = structuredClone(analysis);
unsafe.target.item_name = '<img src=x onerror=alert(1)>';
assert.ok(!purchaseCard(unsafe, 0).includes('<img src=x'), 'Text from responses must be escaped');
console.log('PASS: registered fixtures, card/detail values, shared bar scale, missing/zero/negative amounts, escaped response text');
const market = data.items.find((a) => a.comparison_type === 'market');
assert.ok(priceBars(market).includes('확인된 시중가'));
assert.ok(purchaseDetail(market).includes('가상 판매처'));
assert.ok(purchaseDetail(market).includes('110,000원'));
assert.ok(purchaseDetail(market).includes('포함 비용'));
assert.ok(purchaseDetail(market).includes('기본 안내'));
assert.equal(filterExamples(data.items, { comparison_type: 'market' }).length, 1);
assert.equal(filterExamples(data.items, { comparison_type: 'agency', q: 'missing' }).length, 0);
assert.equal(filterExamples(data.items, { comparison_type: 'agency', status: 'conditions_unknown' }).length, 1);
assert.equal(filterExamples(data.items, { comparison_type: 'agency', agency_id: 'agency-A', status: 'comparable' }).length, 1);
console.log('PASS: market labels/evidence/costs, fallback explanation, type/search/status/agency filters');
