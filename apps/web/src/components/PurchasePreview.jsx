import { useEffect, useState } from 'react';
import Drawer from './Drawer.jsx';
import { filterExamples } from '../../purchase-repository.js';
import { money, percentage, statusLabels } from '../../purchase-card.js';
import examples from '../../assets/purchase-examples.json';

export async function getApi(path, signal) {
  const response = await fetch(`/api${path}`, { signal });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}
function PriceBars({ analysis }) {
  const values = [analysis.target.unit_price, analysis.reference_unit_price];
  const max = Math.max(0, ...values.map((v) => Number(v) || 0));
  return values.map((value, index) => <div key={index}><div className="purchase-price-label"><span>{index === 0 ? '기관 구매 단가' : analysis.comparison_type === 'market' ? '확인된 시중가' : '다른 기관 구매 단가 중앙값'}</span><strong>{money(value)}</strong></div><div className="purchase-track" aria-hidden="true"><div className={`purchase-fill ${index === 0 ? 'purchase-target' : ''}`} style={{ width: `${value != null && max > 0 ? Math.max(0, Number(value) / max * 100) : 0}%` }} /></div></div>);
}
function Difference({ analysis }) {
  return <div className="purchase-difference"><span>비교 기준 대비 단가 차이</span><strong>{analysis.difference == null ? statusLabels[analysis.status] : <>{money(analysis.difference, true)} <small>({percentage(analysis.difference_pct)})</small></>}</strong></div>;
}
function SourceCard({ record }) {
  let url;
  try { const parsed = new URL(record.source_url); if (['http:', 'https:'].includes(parsed.protocol)) url = parsed.href; } catch { /* No invented URLs. */ }
  return <article className="purchase-source"><strong>{record.agency_name ?? record.seller_name}</strong><p>출처 ID: {record.source_id ?? '확인 불가'}<br />원본 ID: {record.source_record_id ?? record.record_id ?? record.market_price_id}<br />수집일 / 확인일: {record.retrieved_at ?? record.checked_at ?? '확인 불가'}</p>{url ? <a href={url} target="_blank" rel="noopener noreferrer">원본 열기 ↗</a> : <p>{record.synthetic ? '합성 예제: 원본 URL 없음' : '원본 URL 없음 · 출처 ID와 원본 ID로 확인하세요.'}</p>}</article>;
}
function PurchaseDetail({ selected, mode }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    setState({ loading: true });
    const request = mode === 'api' ? getApi(`/purchases/${encodeURIComponent(selected.record_id)}?comparison_type=${selected.comparison_type}`, signal) : Promise.resolve(selected);
    request.then((analysis) => { if (!controller.signal.aborted) setState({ analysis }); }).catch(() => { if (!controller.signal.aborted) setState({ error: true }); });
    return () => controller.abort();
  }, [selected, mode]);
  if (state.loading || state.error) return <div id="purchase-detail"><h2 id="purchase-title">구매 상세</h2><p role="status">{state.error ? '상세를 불러오지 못했습니다. 닫은 뒤 다시 시도하세요.' : '상세를 불러오는 중입니다…'}</p></div>;
  const a = state.analysis, t = a.target, market = a.comparison_type === 'market';
  const included = (value) => value === true ? '포함' : value === false ? '미포함' : '확인 불가';
  return <div id="purchase-detail"><p className="detail-eyebrow">{a.synthetic ? '화면 개발용 합성 예제' : '실제 공개 구매 자료 · 비교 미완료'}</p><h2 id="purchase-title">{t.item_name}</h2><p className="detail-description">{t.agency_name} · {t.model ?? '모델 확인 불가'} · {t.purchased_at}</p>
    <section className="detail-section"><h3>대상 가격</h3><Difference analysis={a} /><PriceBars analysis={a} /><p>수량 {t.quantity ?? '확인 불가'} {t.unit} · 계약 {t.contract_id}<br />{t.price_basis}</p><span className="status">{statusLabels[a.status]}</span><ul>{a.reasons.map((text) => <li key={text}>{text}</li>)}</ul></section>
    <section className="detail-section"><h3>비교 대상</h3>{a.comparison_records.length ? <div className="table-scroll"><table><thead><tr><th>{market ? '판매처' : '기관'}</th><th>날짜</th><th>수량 / 단위</th><th>단가</th></tr></thead><tbody>{a.comparison_records.map((r) => <tr key={r.record_id ?? r.market_price_id}><td>{r.agency_name ?? r.seller_name}</td><td>{r.purchased_at ?? r.checked_at}</td><td>{market ? r.unit : `${r.quantity} ${r.unit}`}</td><td>{money(market ? r.price : r.unit_price)}</td></tr>)}</tbody></table></div> : <p>비교 가능한 자료가 없습니다.</p>}</section>
    <section className="detail-section"><h3>계산식과 비교 범위</h3><p>{a.difference == null ? '비교 자료 또는 조건이 부족하여 계산하지 않았습니다.' : <>{money(t.unit_price)} − {money(a.reference_unit_price)} = {money(a.difference, true)}<br />{money(a.difference, true)} ÷ {money(a.reference_unit_price)} × 100 = {percentage(a.difference_pct)}</>}</p><p>{a.policy_id === 'not-configured' ? '자료 수집 범위' : '비교 기간'} {a.comparison_period.from} ~ {a.comparison_period.to}<br />비교 {a.comparison_count}건 · 근거 {a.evidence_ids.length}건<br />{a.policy_id === 'not-configured' ? '비교 정책 미설정 · 분석 미실행' : `방법 ${a.method_version} · 정책 ${a.policy_id}`}</p><ul>{a.excluded_records.map((r) => <li key={r.id}>제외 {r.id}: {r.reason}</li>)}</ul></section>
    <section className="detail-section"><h3>포함 비용</h3><div className="table-scroll"><table><thead><tr><th>대상 / 비교 기록</th><th>부가세</th><th>배송</th><th>설치</th></tr></thead><tbody>{[t, ...a.comparison_records].map((r) => <tr key={r.record_id ?? r.market_price_id}><td>{r.record_id ?? r.market_price_id}</td><td>{included(r.tax_included)}</td><td>{included(r.delivery_included)}</td><td>{included(r.installation_included)}</td></tr>)}</tbody></table></div></section>
    <section className="detail-section"><h3>AI 설명 <span className="status">기본 안내</span></h3><p>생성형 AI는 연결되지 않았습니다. {a.synthetic ? '표시 수치는 합성 예제입니다.' : a.status === 'unavailable' ? '실제 구매 자료이며 비교 결과는 아직 없습니다.' : '실제 구매 자료와 등록된 비교 결과입니다.'} 가격 차이의 원인이나 위법 여부를 이 자료만으로 판단할 수 없습니다.</p><h4>비교의 한계</h4><ul>{a.limitations.map((text) => <li key={text}>{text}</li>)}</ul><h4>추가로 확인할 사항</h4><p>동일 모델·규격, 계약 시점, 수량과 포함 비용을 원본에서 함께 확인하세요.</p></section>
    <section className="detail-section"><h3>출처 카드</h3>{[t, ...a.comparison_records].map((r) => <SourceCard key={r.record_id ?? r.market_price_id} record={r} />)}</section>
  </div>;
}
const initialFilters = { q: '', agency_id: '', item_id: '', status: '', comparison_type: 'agency', sort: 'purchased_desc' };
export default function PurchasePreview() {
  const [open, setOpen] = useState(false), [mode, setMode] = useState('api');
  const [draft, setDraft] = useState(''), [filters, setFilters] = useState(initialFilters);
  const [options, setOptions] = useState({ agencies: [], items: [] });
  const [result, setResult] = useState({ items: [], total: 0, synthetic: null });
  const [loading, setLoading] = useState(false), [error, setError] = useState(false), [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(null);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    setLoading(true); setError(false); setResult({ items: [], total: 0, synthetic: null });
    const request = async () => {
      let data, available;
      if (mode === 'api') {
        const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
        [available, data] = await Promise.all([getApi('/options', signal), getApi(`/purchases?${params}`, signal)]);
      } else {
        available = Object.fromEntries([['agencies', 'agency'], ['items', 'item']].map(([key, field]) => [key, [...new Map(examples.items.map((a) => [a.target[`${field}_id`], a.target[`${field}_name`]])).entries()].map(([id, name]) => ({ id, name }))]));
        const items = filterExamples(examples.items, filters); data = { items, total: items.length, synthetic: true };
      }
      if (!controller.signal.aborted) { setOptions(available); setResult(data); setLoading(false); }
    };
    request().catch(() => { if (!controller.signal.aborted) { setError(true); setLoading(false); } });
    return () => controller.abort();
  }, [open, mode, filters, retry]);
  const change = (key, value) => { setSelected(null); setFilters((current) => ({ ...current, [key]: value, ...(key === 'item_id' && !value ? { sort: 'purchased_desc' } : {}) })); };
  const dates = result.items.map((a) => a.target.retrieved_at).filter(Boolean).sort();
  return <details className="purchase-preview section" onToggle={(event) => setOpen(event.currentTarget.open)}><summary>구매 카드 조회 <span>실제 자료 / 합성 예제</span></summary><div className="preview-content">
    <p className="preview-notice">{result.synthetic === true ? '화면 개발용 합성 예제입니다. 실제 구매나 분석 결과가 아닙니다.' : result.synthetic === false ? '실제 공개 구매 자료입니다. 비교 분석은 아직 연결되지 않았습니다.' : '자료를 불러와 실제 또는 합성 여부를 확인합니다.'}</p>
    <form className="purchase-search" onSubmit={(event) => { event.preventDefault(); change('q', draft.trim()); }}><label htmlFor="purchase-query">구매 검색</label><div><input id="purchase-query" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={200} placeholder="기관·물품·모델명" /><button type="submit" className="outline-button">검색</button></div></form>
    <div className="purchase-filters"><label>데이터 연결<select value={mode} onChange={(event) => { setSelected(null); setMode(event.target.value); }}><option value="api">실제 구매 자료 API</option><option value="local">정적 합성 예제 (서버 없이)</option></select></label>
      <label>기관<select value={filters.agency_id} onChange={(event) => change('agency_id', event.target.value)}><option value="">전체 기관</option>{options.agencies.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>품목<select value={filters.item_id} onChange={(event) => change('item_id', event.target.value)}><option value="">전체 품목</option>{options.items.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>상태<select value={filters.status} onChange={(event) => change('status', event.target.value)}><option value="">전체 상태</option>{Object.entries(statusLabels).map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
      <label>비교 유형<select value={filters.comparison_type} onChange={(event) => change('comparison_type', event.target.value)}><option value="agency">기관 간</option><option value="market">시중가</option></select></label>
      <label>정렬<select value={filters.sort} onChange={(event) => change('sort', event.target.value)}><option value="purchased_desc">구매일 최신순</option><option value="difference_pct_desc" disabled={!filters.item_id}>차이율 큰 순 (품목 선택 필요)</option></select></label></div>
    <p className="preview-meta">검색어: {filters.q || '전체'} · 기관: {options.agencies.find((o) => o.id === filters.agency_id)?.name ?? '전체'} · 품목: {options.items.find((o) => o.id === filters.item_id)?.name ?? '전체'} · 상태: {statusLabels[filters.status] ?? '전체'} · 비교: {filters.comparison_type === 'agency' ? '기관 간' : '시중가'} · {mode === 'api' ? 'API 조회' : '정적 예제 내 조회'}</p>
    {!loading && !error && <p className="preview-meta">검색 결과 {result.total}건 · 자료 수집 시각(표기된 날짜) {dates.at(-1)?.slice(0, 10) ?? '해당 없음'} · {result.synthetic === false ? '원본 자료 범위' : '예제 비교 기간'} {[...new Set(result.items.map((a) => `${a.comparison_period.from} ~ ${a.comparison_period.to}`))].join(', ') || '해당 없음'}</p>}
    <div role="status" aria-live="polite" id="preview-feedback">{loading ? '불러오는 중입니다…' : error ? <>조회하지 못했습니다. API 서버를 실행하거나 정적 합성 예제로 전환하세요. <button className="outline-button" onClick={() => setRetry((value) => value + 1)}>다시 시도</button></> : !result.items.length ? '검색 결과가 없습니다. 조건을 바꿔보세요.' : ''}</div>
    <div className="purchase-grid">{result.items.map((a) => <article className="purchase-card" key={`${a.record_id}-${a.comparison_type}`}><div className="purchase-top"><span className="status">{statusLabels[a.status]}</span><time>{a.target.purchased_at}</time></div><div className="purchase-icon" aria-hidden="true">▤</div><h3>{a.target.item_name}</h3><p className="purchase-spec">{a.target.model ?? '모델 확인 불가'} · {a.target.specification}</p><p className="purchase-agency">{a.target.agency_name}</p><Difference analysis={a} /><PriceBars analysis={a} /><div className="purchase-bottom"><span>비교 {a.comparison_count}건 · 근거 {a.evidence_ids.length}건</span><button onClick={() => setSelected(a)} aria-label={`${a.target.agency_name} ${a.target.item_name} 자세히 보기`}>자세히 보기 ↗</button></div></article>)}</div>
    {selected && <Drawer title={selected.synthetic ? "합성 구매 예제 상세" : "구매 상세"} labelledBy="purchase-title" onClose={() => setSelected(null)}><PurchaseDetail selected={selected} mode={mode} /></Drawer>}
  </div></details>;
}
