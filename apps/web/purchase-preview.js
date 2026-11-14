import { purchaseCard, purchaseDetail } from './purchase-card.js';
import { apiGet, filterExamples } from './purchase-repository.js';
const $ = (id) => document.getElementById(id);
let analyses = [], localData, opener, query = '', listRequest, detailRequest;
const dialog = $('purchase-dialog');
const ids = ['purchase-mode', 'purchase-agency', 'purchase-item', 'purchase-status', 'purchase-type', 'purchase-sort'];
function filters() {
  return { q: query, agency_id: $('purchase-agency').value, item_id: $('purchase-item').value, status: $('purchase-status').value, comparison_type: $('purchase-type').value, sort: $('purchase-sort').value };
}
async function local(signal) {
  if (!localData) {
    const response = await fetch('assets/purchase-examples.json', { signal });
    if (!response.ok) throw new Error('Example load failed');
    const data = await response.json();
    if (!Array.isArray(data.items) || data.items.some((a) => a.synthetic !== true)) throw new Error('Synthetic examples expected');
    localData = data.items;
  }
  return localData;
}
async function loadExamples(refreshOptions = false) {
  listRequest?.abort();
  const controller = new AbortController();
  listRequest = controller;
  const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
  const mode = $('purchase-mode').value;
  $('purchase-cards').textContent = '';
  $('preview-meta').textContent = '';
  $('purchase-conditions').textContent = '';
  $('preview-feedback').textContent = '합성 예제를 불러오는 중입니다…';
  try {
    if (refreshOptions) {
      let options;
      if (mode === 'api') options = await apiGet('/api/options', signal);
      else {
        const items = await local(signal);
        options = Object.fromEntries([['agencies', 'agency'], ['items', 'item']].map(([key, field]) => [key, [...new Map(items.map((a) => [a.target[`${field}_id`], a.target[`${field}_name`]])).entries()].map(([id, name]) => ({ id, name }))]));
      }
      for (const [id, key] of [['purchase-agency', 'agencies'], ['purchase-item', 'items']]) {
        const previous = $(id).value;
        $(id).length = 1;
        for (const option of options[key]) $(id).add(new Option(option.name, option.id));
        $(id).value = [...$(id).options].some((option) => option.value === previous) ? previous : '';
      }
    }
    const f = filters();
    const params = new URLSearchParams(Object.entries(f).filter(([, value]) => value));
    let data;
    if (mode === 'api') data = await apiGet(`/api/purchases?${params}`, signal);
    else { const matches = filterExamples(await local(signal), f); data = { items: matches, total: matches.length }; }
    if (controller.signal.aborted) return;
    analyses = data.items;
    const dates = analyses.map((a) => a.target.retrieved_at).filter(Boolean).sort();
    const periods = [...new Set(analyses.map((a) => `${a.comparison_period.from} ~ ${a.comparison_period.to}`))];
    $('preview-meta').textContent = `검색 결과 ${data.total}건 · 합성 예제 기준일 ${dates.at(-1)?.slice(0, 10) ?? '해당 없음'} · 비교 기간 ${periods.join(', ') || '해당 없음'}`;
    $('purchase-conditions').textContent = `검색어: ${query || '전체'} · 기관: ${$('purchase-agency').selectedOptions[0].text} · 품목: ${$('purchase-item').selectedOptions[0].text} · 상태: ${$('purchase-status').selectedOptions[0].text} · 비교: ${$('purchase-type').selectedOptions[0].text} · ${mode === 'api' ? 'API 조회' : '정적 예제 내 조회'}`;
    $('purchase-cards').innerHTML = analyses.map(purchaseCard).join('');
    $('preview-feedback').textContent = analyses.length ? '' : '검색 결과가 없습니다. 조건을 바꿔보세요.';
  } catch {
    if (controller.signal.aborted) return;
    $('preview-feedback').innerHTML = '조회하지 못했습니다. API 모드라면 서버를 실행하거나 정적 합성 예제로 전환하세요. <button class="outline-button" id="retry-examples">다시 시도</button>';
    $('retry-examples').onclick = () => loadExamples(true);
  }
}
async function showDetail(analysis, button) {
  opener = button;
  dialog.showModal();
  $('purchase-detail').innerHTML = '<h2 id="purchase-title">구매 상세</h2><p role="status">상세를 불러오는 중입니다…</p>';
  $('purchase-close').focus();
  const controller = new AbortController();
  detailRequest = controller;
  try {
    const detail = $('purchase-mode').value === 'api' ? await apiGet(`/api/purchases/${encodeURIComponent(analysis.record_id)}?comparison_type=${analysis.comparison_type}`, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)])) : analysis;
    if (controller.signal.aborted) return;
    $('purchase-detail').innerHTML = purchaseDetail(detail);
  } catch {
    if (!controller.signal.aborted) $('purchase-detail').innerHTML = '<h2 id="purchase-title">상세 조회 실패</h2><p>닫은 뒤 다시 시도하세요. 목록은 유지됩니다.</p>';
  }
}
$('purchase-cards').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-purchase-index]');
  if (button && analyses[Number(button.dataset.purchaseIndex)]) showDetail(analyses[Number(button.dataset.purchaseIndex)], button);
});
$('purchase-search').onsubmit = (event) => { event.preventDefault(); query = $('purchase-query').value.trim(); loadExamples(); };
for (const id of ids) $(id).onchange = () => {
  $('purchase-sort').options[1].disabled = !$('purchase-item').value;
  if (!$('purchase-item').value) $('purchase-sort').value = 'purchased_desc';
  loadExamples(id === 'purchase-mode');
};
$('purchase-close').onclick = () => dialog.close();
dialog.addEventListener('close', () => { detailRequest?.abort(); opener?.focus(); });
dialog.addEventListener('click', (event) => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});
// The separate preview never computes province scores.
$('purchase-preview').addEventListener('toggle', () => { if ($('purchase-preview').open) loadExamples(true); });
