import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { filterExamples } from './purchase-repository.js';
const fixture = JSON.parse(readFileSync(new URL('./assets/purchase-examples.json', import.meta.url)));
const calls = [], elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: '', innerHTML: '', textContent: '', open: false, options: [], handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
    get selectedOptions() { return [{ text: this.value || '전체' }]; },
    set length(value) { this.options.length = value; },
    add(option) { this.options.push(option); },
    showModal() { this.open = true; }, close() { this.open = false; this.handlers.close?.(); }, focus() { this.focused = true; },
  });
  return elements.get(id);
}
globalThis.document = { getElementById: element };
globalThis.Option = class { constructor(text, value) { this.text = text; this.value = value; } };
element('purchase-mode').value = 'api';
element('purchase-type').value = 'agency';
element('purchase-sort').value = 'purchased_desc';
element('purchase-sort').options = [{}, {}];
for (const id of ['purchase-agency', 'purchase-item']) element(id).options = [{ value: '' }];
let fail = false;
globalThis.fetch = async (input) => {
  calls.push(input);
  if (fail) throw new Error('Offline');
  const url = new URL(input, 'http://localhost:5173');
  let data;
  if (url.pathname === '/api/options') data = { agencies: [{ id: 'agency-A', name: '예시기관 A' }], items: [{ id: 'demo-item-1', name: '예시 물품' }] };
  else if (url.pathname === '/api/purchases') { const items = filterExamples(fixture.items, Object.fromEntries(url.searchParams)); data = { items, total: items.length }; }
  else if (url.pathname.startsWith('/api/purchases/')) data = fixture.items.find((a) => a.record_id === url.pathname.split('/').at(-1) && a.comparison_type === url.searchParams.get('comparison_type'));
  else data = fixture;
  return { ok: true, json: async () => data };
};
await import('./purchase-preview.js');
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
element('purchase-preview').open = true;
element('purchase-preview').handlers.toggle();
await settle();
assert.ok(element('purchase-cards').innerHTML.includes('+30,000원'));
element('purchase-query').value = 'missing';
element('purchase-search').onsubmit({ preventDefault() {} });
await settle();
assert.ok(calls.at(-1).includes('q=missing'));
assert.ok(element('preview-feedback').textContent.includes('검색 결과가 없습니다'));
element('purchase-query').value = '';
element('purchase-search').onsubmit({ preventDefault() {} });
await settle();
element('purchase-type').value = 'market';
element('purchase-type').onchange();
await settle();
assert.ok(calls.at(-1).includes('comparison_type=market'));
assert.ok(element('purchase-cards').innerHTML.includes('확인된 시중가'));
const trigger = { dataset: { purchaseIndex: '0' }, focus() { this.focused = true; } };
element('purchase-cards').handlers.click({ target: { closest: () => trigger } });
await settle();
assert.ok(calls.at(-1).includes('/demo-A?comparison_type=market'));
assert.ok(element('purchase-detail').innerHTML.includes('가상 판매처'));
element('purchase-close').onclick();
assert.equal(trigger.focused, true);
fail = true;
element('purchase-type').onchange();
await settle();
assert.equal(element('purchase-cards').textContent, '');
assert.ok(element('preview-feedback').innerHTML.includes('조회하지 못했습니다'));
console.log('PASS: API submit/query, type reload, market detail ID/type, close/focus, failed request feedback');
