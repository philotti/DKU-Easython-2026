import { useEffect, useRef, useState } from 'react';
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
function Difference({ analysis, preliminary = false, emptyLabel }) {
  return <div className="purchase-difference"><span>{preliminary ? '조건 미확인 참고 단가 차이' : '비교 기준 대비 단가 차이'}</span><strong>{analysis.difference == null ? (emptyLabel ?? statusLabels[analysis.status]) : <>{money(analysis.difference, true)} <small>({percentage(analysis.difference_pct)})</small></>}</strong></div>;
}
function SourceCard({ record }) {
  let url;
  try { const parsed = new URL(record.source_url); if (['http:', 'https:'].includes(parsed.protocol)) url = parsed.href; } catch { /* No invented URLs. */ }
  return <article className="purchase-source"><strong>{record.agency_name ?? record.seller_name}</strong><p>출처 ID: {record.source_id ?? '확인 불가'}<br />원본 ID: {record.source_record_id ?? record.record_id ?? record.market_price_id}<br />수집일 / 확인일: {record.retrieved_at ?? record.checked_at ?? '확인 불가'}</p>{url ? <a href={url} target="_blank" rel="noopener noreferrer">원본 열기 ↗</a> : <p>{record.synthetic ? '합성 예제: 원본 URL 없음' : '원본 URL 없음 · 출처 ID와 원본 ID로 확인하세요.'}</p>}</article>;
}
function PurchaseDetail({ selected, mode }) {
  const [state, setState] = useState({ loading: true });
  const [explanation, setExplanation] = useState({ loading: true });
  const [preliminary, setPreliminary] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    setState({ loading: true });
    const request = mode === 'api' ? getApi(`/purchases/${encodeURIComponent(selected.record_id)}?comparison_type=${selected.comparison_type}`, signal) : Promise.resolve(selected);
    request.then((analysis) => { if (!controller.signal.aborted) setState({ analysis }); }).catch(() => { if (!controller.signal.aborted) setState({ error: true }); });
    return () => controller.abort();
  }, [selected, mode]);
  useEffect(() => {
    if (mode !== 'api') { setPreliminary({ local: true }); return; }
    const controller = new AbortController();
    setPreliminary({ loading: true });
    getApi(`/preliminary/${encodeURIComponent(selected.record_id)}?comparison_type=${selected.comparison_type}`, AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then((data) => { if (!controller.signal.aborted) setPreliminary({ data }); })
      .catch(() => { if (!controller.signal.aborted) setPreliminary({ error: true }); });
    return () => controller.abort();
  }, [selected, mode]);
  useEffect(() => {
    if (mode !== 'api') { setExplanation({ local: true }); return; }
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
    setExplanation({ loading: true });
    getApi(`/explanations/${encodeURIComponent(selected.record_id)}?comparison_type=${selected.comparison_type}`, signal)
      .then((data) => { if (!controller.signal.aborted) setExplanation({ data }); })
      .catch(() => { if (!controller.signal.aborted) setExplanation({ error: true }); });
    return () => controller.abort();
  }, [selected, mode]);
  if (state.loading || state.error) return <div id="purchase-detail"><h2 id="purchase-title">구매 상세</h2><p role="status">{state.error ? '상세를 불러오지 못했습니다. 닫은 뒤 다시 시도하세요.' : '상세를 불러오는 중입니다…'}</p></div>;
  const a = state.analysis, t = a.target, market = a.comparison_type === 'market';
  const included = (value) => value === true ? '포함' : value === false ? '미포함' : '확인 불가';
  return <div id="purchase-detail"><p className="detail-eyebrow">{a.synthetic ? '화면 개발용 합성 예제' : '실제 공개 구매 자료'}</p><h2 id="purchase-title">{t.item_name}</h2><p className="detail-description">{t.agency_name} · {t.model ?? '모델 확인 불가'} · {t.purchased_at}</p>
    {mode === 'api' && <section className="detail-section"><h3>조건 미확인 참고 비교</h3>{preliminary.loading ? <p role="status">참고 가격을 계산하는 중입니다…</p> : preliminary.error ? <p>참고 가격을 불러오지 못했습니다.</p> : preliminary.data && <><p>동일 제품·단위의 {market ? '연결된 시중가' : '다른 기관 구매 단가'} 중앙값과 비교한 참고 수치입니다.</p>{preliminary.data.difference == null ? <p>{preliminary.data.reasons.join(' ')}</p> : <><p>기관 구매 단가 {money(t.unit_price)}<br />참고 가격 중앙값 {money(preliminary.data.reference_unit_price)}<br /><strong>단가 차이 {money(preliminary.data.difference, true)} ({percentage(preliminary.data.difference_pct)})</strong><br />참고 자료 {preliminary.data.comparison_count}건</p><details><summary>참고 자료와 출처 보기</summary>{preliminary.data.comparison_records.map((record) => <div key={record.record_id ?? record.market_price_id}><p>단가 {money(record.unit_price ?? record.price)} · {record.purchased_at ?? record.checked_at} · 수량 {record.quantity ?? '확인 불가'} {record.unit}</p><SourceCard record={record} /></div>)}</details></>}<ul>{preliminary.data.limitations.map((text) => <li key={text}>{text}</li>)}</ul></>}</section>}
    <section className="detail-section"><h3>엄격한 비교 기준</h3><p>아래는 계약 상태와 비용 조건이 확인된 자료만 사용하는 비교 결과입니다.</p><Difference analysis={a} /><PriceBars analysis={a} /><p>수량 {t.quantity ?? '확인 불가'} {t.unit} · 계약 {t.contract_id}<br />{t.price_basis}</p><span className="status">엄격 비교: {statusLabels[a.status]}</span><ul>{a.reasons.map((text) => <li key={text}>{text}</li>)}</ul></section>
    <section className="detail-section"><h3>비교 대상</h3>{a.comparison_records.length ? <div className="table-scroll"><table><thead><tr><th>{market ? '판매처' : '기관'}</th><th>날짜</th><th>수량 / 단위</th><th>단가</th></tr></thead><tbody>{a.comparison_records.map((r) => <tr key={r.record_id ?? r.market_price_id}><td>{r.agency_name ?? r.seller_name}</td><td>{r.purchased_at ?? r.checked_at}</td><td>{market ? r.unit : `${r.quantity} ${r.unit}`}</td><td>{money(market ? r.price : r.unit_price)}</td></tr>)}</tbody></table></div> : <p>비교 가능한 자료가 없습니다.</p>}</section>
    <section className="detail-section"><h3>계산식과 비교 범위</h3><p>{a.difference == null ? '비교 자료 또는 조건이 부족하여 계산하지 않았습니다.' : <>{money(t.unit_price)} − {money(a.reference_unit_price)} = {money(a.difference, true)}<br />{money(a.difference, true)} ÷ {money(a.reference_unit_price)} × 100 = {percentage(a.difference_pct)}</>}</p><p>{a.policy_id === 'not-configured' ? '자료 수집 범위' : '비교 기간'} {a.comparison_period.from} ~ {a.comparison_period.to}<br />비교 {a.comparison_count}건 · 근거 {a.evidence_ids.length}건<br />{a.policy_id === 'not-configured' ? '비교 정책 미설정 · 분석 미실행' : `방법 ${a.method_version} · 정책 ${a.policy_id}`}</p><ul>{a.excluded_records.map((r) => <li key={r.id}>제외 {r.id}: {r.reason}</li>)}</ul></section>
    <section className="detail-section"><h3>포함 비용</h3><div className="table-scroll"><table><thead><tr><th>대상 / 비교 기록</th><th>부가세</th><th>배송</th><th>설치</th></tr></thead><tbody>{[t, ...a.comparison_records].map((r) => <tr key={r.record_id ?? r.market_price_id}><td>{r.record_id ?? r.market_price_id}</td><td>{included(r.tax_included)}</td><td>{included(r.delivery_included)}</td><td>{included(r.installation_included)}</td></tr>)}</tbody></table></div></section>
    <section className="detail-section"><h3>AI 설명 {explanation.data && <span className="status">{explanation.data.mode === 'ai' ? 'AI 확인 사항' : '기본 안내'}</span>}</h3>{explanation.loading ? <p role="status">설명을 불러오는 중입니다…</p> : explanation.data ? <><p>{explanation.data.summary}</p><ul>{explanation.data.cautions.map((text) => <li key={text}>{text}</li>)}</ul></> : <><p>{explanation.error ? '설명을 불러오지 못했습니다.' : '합성 예제에는 기본 안내를 표시합니다.'} 가격 차이의 원인이나 위법 여부를 이 자료만으로 판단할 수 없습니다.</p><ul>{a.limitations.map((text) => <li key={text}>{text}</li>)}</ul></>}<h4>추가로 확인할 사항</h4><p>동일 모델·규격, 계약 시점, 수량과 포함 비용을 원본에서 함께 확인하세요.</p></section>
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
  const [loadingMore, setLoadingMore] = useState(false), [moreError, setMoreError] = useState(false);
  const sentinel = useRef(null), moreRequest = useRef(null), loadingMoreRef = useRef(false);
  const [selected, setSelected] = useState(null);
  const [referenceResults, setReferenceResults] = useState({});
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    moreRequest.current?.abort(); loadingMoreRef.current = false;
    setLoadingMore(false); setMoreError(false);
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
    return () => { controller.abort(); moreRequest.current?.abort(); };
  }, [open, mode, filters, retry]);
  useEffect(() => {
    if (!open || mode !== 'api' || !result.items.length) return;
    const kind = filters.comparison_type;
    const missing = result.items.filter((item) => item.comparison_type === kind && !(Object.hasOwn(referenceResults, `${kind}:${item.record_id}`))).slice(0, 100);
    if (!missing.length) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ comparison_type: kind });
    missing.forEach((item) => params.append('record_id', item.record_id));
    getApi(`/preliminary?${params}`, AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then((data) => {
        if (controller.signal.aborted) return;
        const found = new Map(data.items.map((item) => [item.record_id, item]));
        setReferenceResults((previous) => ({ ...previous, ...Object.fromEntries(missing.map((item) => [`${kind}:${item.record_id}`, found.get(item.record_id) ?? { error: true }])) }));
      })
      .catch(() => {
        if (!controller.signal.aborted) setReferenceResults((previous) => ({ ...previous, ...Object.fromEntries(missing.map((item) => [`${kind}:${item.record_id}`, { error: true }])) }));
      });
    return () => controller.abort();
  }, [open, mode, filters.comparison_type, result.items, referenceResults]);
  const loadMore = async () => {
    if (!open || mode !== 'api' || loading || loadingMoreRef.current || result.items.length >= result.total) return;
    const controller = new AbortController();
    moreRequest.current = controller; loadingMoreRef.current = true; setLoadingMore(true); setMoreError(false);
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    params.set('page', String((result.page ?? 1) + 1));
    params.set('page_size', String(result.page_size ?? 20));
    try {
      const data = await getApi(`/purchases?${params}`, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]));
      if (!controller.signal.aborted) {
        setResult((current) => ({ ...data, items: [...current.items, ...data.items] }));
        if (!data.items.length && data.total > result.items.length) setMoreError(true);
      }
    } catch {
      if (!controller.signal.aborted) setMoreError(true);
    } finally {
      if (!controller.signal.aborted) { loadingMoreRef.current = false; setLoadingMore(false); }
    }
  };
  useEffect(() => {
    if (!open || mode !== 'api' || loading || loadingMore || moreError || !sentinel.current || result.items.length >= result.total || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { observer.disconnect(); loadMore(); }
    }, { rootMargin: '400px' });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [open, mode, filters, loading, loadingMore, moreError, result]);
  const change = (key, value) => { setSelected(null); setFilters((current) => ({ ...current, [key]: value, ...(key === 'item_id' && !value ? { sort: 'purchased_desc' } : {}) })); };
  const dates = result.items.map((a) => a.target.retrieved_at).filter(Boolean).sort();
  return <details className="purchase-preview section" onToggle={(event) => setOpen(event.currentTarget.open)}><summary>구매 카드 조회 <span>실제 자료 / 합성 예제</span></summary><div className="preview-content">
    <p className="preview-notice">{result.synthetic === true ? '화면 개발용 합성 예제입니다. 실제 구매나 분석 결과가 아닙니다.' : result.synthetic === false ? '실제 구매 자료의 참고 가격 차이입니다. 계약 상태와 세금·배송·설치 등 조건은 확인되지 않았으며 가격 차이만으로 이상 거래를 판단할 수 없습니다.' : '자료를 불러와 실제 또는 합성 여부를 확인합니다.'}</p>
    <form className="purchase-search" onSubmit={(event) => { event.preventDefault(); change('q', draft.trim()); }}><label htmlFor="purchase-query">구매 검색</label><div><input id="purchase-query" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={200} placeholder="기관·물품·모델명" /><button type="submit" className="outline-button">검색</button></div></form>
    <div className="purchase-filters"><label>데이터 연결<select value={mode} onChange={(event) => { setSelected(null); setMode(event.target.value); }}><option value="api">실제 구매 자료 API</option><option value="local">정적 합성 예제 (서버 없이)</option></select></label>
      <label>기관<select value={filters.agency_id} onChange={(event) => change('agency_id', event.target.value)}><option value="">전체 기관</option>{options.agencies.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>품목<select value={filters.item_id} onChange={(event) => change('item_id', event.target.value)}><option value="">전체 품목</option>{options.items.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>엄격 비교 상태<select value={filters.status} onChange={(event) => change('status', event.target.value)}><option value="">전체 상태</option>{Object.entries(statusLabels).map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
      <label>비교 유형<select value={filters.comparison_type} onChange={(event) => change('comparison_type', event.target.value)}><option value="agency">기관 간</option><option value="market">시중가</option></select></label>
      <label>정렬<select value={filters.sort} onChange={(event) => change('sort', event.target.value)}><option value="purchased_desc">구매일 최신순</option><option value="difference_pct_desc" disabled={!filters.item_id}>엄격 비교 차이율 순 (품목 선택 필요)</option></select></label></div>
    <p className="preview-meta">검색어: {filters.q || '전체'} · 기관: {options.agencies.find((o) => o.id === filters.agency_id)?.name ?? '전체'} · 품목: {options.items.find((o) => o.id === filters.item_id)?.name ?? '전체'} · 상태: {statusLabels[filters.status] ?? '전체'} · 비교: {filters.comparison_type === 'agency' ? '기관 간' : '시중가'} · {mode === 'api' ? 'API 조회' : '정적 예제 내 조회'}</p>
    {!loading && !error && <p className="preview-meta">검색 결과 {result.total}건 · 자료 수집 시각(표기된 날짜) {dates.at(-1)?.slice(0, 10) ?? '해당 없음'} · {result.synthetic === false ? '원본 자료 범위' : '예제 비교 기간'} {[...new Set(result.items.map((a) => `${a.comparison_period.from} ~ ${a.comparison_period.to}`))].join(', ') || '해당 없음'}</p>}
    <div role="status" aria-live="polite" id="preview-feedback">{loading ? '불러오는 중입니다…' : error ? <>조회하지 못했습니다. API 서버를 실행하거나 정적 합성 예제로 전환하세요. <button className="outline-button" onClick={() => setRetry((value) => value + 1)}>다시 시도</button></> : !result.items.length ? '검색 결과가 없습니다. 조건을 바꿔보세요.' : ''}</div>
    <div className="purchase-grid">{result.items.map((a) => {
      const reference = mode === 'api' ? referenceResults[`${a.comparison_type}:${a.record_id}`] : null;
      const useReference = a.status !== 'comparable' && reference && !reference.error;
      const display = useReference ? { ...a, reference_unit_price: reference.reference_unit_price, difference: reference.difference, difference_pct: reference.difference_pct } : a;
      const label = mode !== 'api' || a.status === 'comparable' ? statusLabels[a.status] : !reference ? '참고 가격 확인 중' : reference.error ? '참고 가격 조회 실패' : reference.difference == null ? '참고 자료 부족' : '조건 미확인 참고 비교';
      return <article className="purchase-card" key={`${a.record_id}-${a.comparison_type}`}><div className="purchase-top"><span className="status">{label}</span><time>{a.target.purchased_at}</time></div><div className="purchase-icon" aria-hidden="true">▤</div><h3>{a.target.item_name}</h3><p className="purchase-spec">{a.target.model ?? '모델 확인 불가'} · {a.target.specification}</p><p className="purchase-agency">{a.target.agency_name}</p><Difference analysis={display} preliminary={useReference} emptyLabel={mode === 'api' && a.status !== 'comparable' ? label : undefined} /><PriceBars analysis={display} /><div className="purchase-bottom"><span>{useReference ? `참고 ${reference.comparison_count}건 · 조건 확인 필요` : `비교 ${a.comparison_count}건 · 근거 ${a.evidence_ids.length}건`}</span><button onClick={() => setSelected(a)} aria-label={`${a.target.agency_name} ${a.target.item_name} 자세히 보기`}>자세히 보기 ↗</button></div></article>;
    })}</div>
    {mode === 'api' && result.items.length > 0 && result.items.length < result.total && <div ref={sentinel} role="status" aria-live="polite"><p>{loadingMore ? '다음 구매 기록을 불러오는 중입니다…' : moreError ? '다음 구매 기록을 불러오지 못했습니다.' : `${result.total}건 중 ${result.items.length}건 표시`}</p><button className="outline-button" onClick={loadMore} disabled={loadingMore}>{moreError ? '다시 시도' : '더 보기'}</button></div>}
    {selected && <Drawer title={selected.synthetic ? "합성 구매 예제 상세" : "구매 상세"} labelledBy="purchase-title" onClose={() => setSelected(null)}><PurchaseDetail selected={selected} mode={mode} /></Drawer>}
  </div></details>;
}
