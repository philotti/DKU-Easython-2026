// Display the registered analysis values; do not calculate comparison results here.
export const statusLabels = {
  comparable: '비교 가능',
  insufficient_data: '비교 자료 부족',
  conditions_unknown: '조건 확인 필요',
  unavailable: '분석 불가',
};
export const escapeHtml = (value) => String(value ?? '확인 불가').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const decimal = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
export function money(value, signed = false) {
  const amount = decimal(value);
  return amount === null ? '확인 불가' : `${signed && amount > 0 ? '+' : ''}${amount.toLocaleString('ko-KR')}원`;
}
export function percentage(value) {
  const amount = decimal(value);
  return amount === null ? '확인 불가' : `${amount > 0 ? '+' : ''}${amount.toLocaleString('ko-KR')}%`;
}
export function differenceMarkup(analysis) {
  return `<div class="purchase-difference"><span>비교 기준 대비 단가 차이</span><strong>${analysis.difference == null ? escapeHtml(statusLabels[analysis.status] ?? '계산 불가') : `${money(analysis.difference, true)} <small>(${percentage(analysis.difference_pct)})</small>`}</strong></div>`;
}
export function priceBars(analysis) {
  const amounts = [decimal(analysis.target.unit_price), decimal(analysis.reference_unit_price)];
  const max = Math.max(0, ...amounts.filter((value) => value !== null));
  const referenceLabel = analysis.comparison_type === 'market' ? '확인된 시중가' : '다른 기관 구매 단가 중앙값';
  return amounts.map((amount, index) => `<div class="purchase-price-label"><span>${index === 0 ? '기관 구매 단가' : referenceLabel}</span><strong>${money(amount)}</strong></div><div class="purchase-track" aria-hidden="true"><div class="purchase-fill ${index === 0 ? 'purchase-target' : ''}" style="width:${amount !== null && max > 0 ? Math.max(0, amount / max * 100) : 0}%"></div></div>`).join('');
}
export function purchaseCard(analysis, index) {
  const target = analysis.target;
  return `<article class="purchase-card"><div class="purchase-top"><span class="status">${escapeHtml(statusLabels[analysis.status] ?? '분석 불가')}</span><time>${escapeHtml(target.purchased_at)}</time></div><div class="purchase-icon" aria-hidden="true">▤</div><h3>${escapeHtml(target.item_name)}</h3><p class="purchase-spec">${escapeHtml(target.model)} · ${escapeHtml(target.specification)}</p><p class="purchase-agency">${escapeHtml(target.agency_name)}</p>${differenceMarkup(analysis)}${priceBars(analysis)}<div class="purchase-bottom"><span>비교 ${escapeHtml(analysis.comparison_count)}건 · 근거 ${analysis.evidence_ids.length}건</span><button data-purchase-index="${index}" aria-label="${escapeHtml(target.agency_name)} ${escapeHtml(target.item_name)} 합성 예제 자세히 보기">자세히 보기 ↗</button></div></article>`;
}
export { purchaseDetail } from './purchase-detail.js';
