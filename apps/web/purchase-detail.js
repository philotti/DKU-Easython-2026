import { escapeHtml as e, money, percentage, differenceMarkup, priceBars, statusLabels } from './purchase-card.js';
const included = (value) => value === true ? '포함' : value === false ? '미포함' : '확인 불가';
function sourceCard(record) {
  let link = '';
  try {
    const url = new URL(record.source_url);
    if (['http:', 'https:'].includes(url.protocol)) link = `<a href="${e(url.href)}" target="_blank" rel="noopener noreferrer">원본 열기 ↗</a>`;
  } catch { /* Missing URLs are not invented. */ }
  return `<article class="purchase-source"><strong>${e(record.agency_name ?? record.seller_name)}</strong><p>출처 ID: ${e(record.source_id)}<br>원본 ID: ${e(record.source_record_id ?? record.record_id ?? record.market_price_id)}<br>수집일 / 확인일: ${e(record.retrieved_at ?? record.checked_at)}</p>${link || '<p>원본 URL 없음 · 공통 예제: tests/fixtures/contracts-v1/</p>'}</article>`;
}
export function purchaseDetail(a) {
  const t = a.target;
  const market = a.comparison_type === 'market';
  return `<p class="detail-eyebrow">화면 개발용 합성 예제</p><h2 id="purchase-title">${e(t.item_name)}</h2><p class="detail-description">${e(t.agency_name)} · ${e(t.model)} · ${e(t.purchased_at)}</p>
    <section class="detail-section"><h3>대상 가격</h3>${differenceMarkup(a)}${priceBars(a)}<dl><dt>수량 / 단위</dt><dd>${e(t.quantity)} ${e(t.unit)}</dd><dt>구매 단가</dt><dd>${money(t.unit_price)}</dd><dt>계약 ID</dt><dd>${e(t.contract_id)}</dd><dt>가격 의미</dt><dd>${e(t.price_basis)}</dd></dl><p>${e(statusLabels[a.status])}</p><ul>${a.reasons.map((reason) => `<li>${e(reason)}</li>`).join('')}</ul></section>
    <section class="detail-section"><h3>비교 대상</h3>${a.comparison_records.length ? `<div class="table-scroll"><table><thead><tr><th>${market ? '판매처' : '기관'}</th><th>구매일 / 확인일</th><th>수량 / 단위</th><th>단가</th></tr></thead><tbody>${a.comparison_records.map((r) => `<tr><td>${e(r.agency_name ?? r.seller_name)}</td><td>${e(r.purchased_at ?? r.checked_at)}</td><td>${market ? e(r.unit) : `${e(r.quantity)} ${e(r.unit)}`}</td><td>${money(market ? r.price : r.unit_price)}</td></tr>`).join('')}</tbody></table></div>` : '<p>비교 가능한 구매·시중가 자료가 없습니다.</p>'}</section>
    <section class="detail-section"><h3>계산식과 비교 범위</h3><p>${a.difference == null ? '비교 자료 또는 조건이 부족하여 계산하지 않았습니다.' : `${money(t.unit_price)} − ${money(a.reference_unit_price)} = ${money(a.difference, true)}<br>${money(a.difference, true)} ÷ ${money(a.reference_unit_price)} × 100 = ${percentage(a.difference_pct)}`}</p><p>기간: ${e(a.comparison_period.from)} ~ ${e(a.comparison_period.to)}<br>비교 ${e(a.comparison_count)}건 · 근거 ${a.evidence_ids.length}건<br>방법: ${e(a.method_version)} · 정책: ${e(a.policy_id)}</p><ul>${a.excluded_records.map((r) => `<li>제외 ${e(r.id)}: ${e(r.reason)}</li>`).join('')}</ul></section>
    <section class="detail-section"><h3>포함 비용</h3><div class="table-scroll"><table><thead><tr><th>대상 / 비교 기록</th><th>부가세</th><th>배송</th><th>설치</th></tr></thead><tbody>${[t, ...a.comparison_records].map((r) => `<tr><td>${e(r.record_id ?? r.market_price_id)}</td><td>${included(r.tax_included)}</td><td>${included(r.delivery_included)}</td><td>${included(r.installation_included)}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="detail-section"><h3>AI 설명 <span class="status">기본 안내</span></h3><p>생성형 AI는 연결되지 않았습니다. 표시된 수치와 계산식은 등록된 합성 분석 결과입니다. 가격 차이의 원인이나 위법 여부를 이 자료만으로 판단할 수 없습니다.</p><h4>비교의 한계</h4><ul>${a.limitations.map((text) => `<li>${e(text)}</li>`).join('')}</ul><h4>추가로 확인할 사항</h4><p>동일 모델·규격, 계약 시점, 수량과 포함 비용을 원본에서 함께 확인하세요.</p></section>
    <section class="detail-section"><h3>출처 카드</h3>${[t, ...a.comparison_records].map(sourceCard).join('')}</section>`;
}
