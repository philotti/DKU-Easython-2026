import { useEffect, useRef, useState } from 'react';
import Drawer from './Drawer.jsx';
import { agencyName } from '../agency-name.js';
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
  return values.map((value, index) => <div key={index}><div className="purchase-price-label"><span>{index === 0 ? '기관 구매 단가' : analysis.comparison_type === 'market' ? '확인된 시중가' : '다른 기관별 단가 중앙값의 중앙값'}</span><strong>{money(value)}</strong></div><div className="purchase-track" aria-hidden="true"><div className={`purchase-fill ${index === 0 ? 'purchase-target' : ''}`} style={{ width: `${value != null && max > 0 ? Math.max(0, Number(value) / max * 100) : 0}%` }} /></div></div>);
}
function Difference({ analysis, preliminary = false, emptyLabel }) {
  return <div className="purchase-difference"><span>{preliminary ? '조건 미확인 참고 단가 차이' : '비교 기준 대비 단가 차이'}</span><strong>{analysis.difference == null ? (emptyLabel ?? statusLabels[analysis.status]) : <>{money(analysis.difference, true)} <small>({percentage(analysis.difference_pct)})</small></>}</strong></div>;
}
function SourceCard({ record }) {
  let url;
  try { const parsed = new URL(record.source_url); if (['http:', 'https:'].includes(parsed.protocol)) url = parsed.href; } catch { /* No invented URLs. */ }
  return <article className="purchase-source"><strong>{agencyName(record.agency_name) ?? record.seller_name}</strong><p>{record.agency_name && agencyName(record.agency_name) !== record.agency_name && <>원본 기관명: {record.agency_name}<br /></>}출처 ID: {record.source_id ?? '확인 불가'}<br />원본 ID: {record.source_record_id ?? record.record_id ?? record.market_price_id}<br />수집일 / 확인일: {record.retrieved_at ?? record.checked_at ?? '확인 불가'}</p>{url ? <a href={url} target="_blank" rel="noopener noreferrer">원본 열기 ↗</a> : <p>{record.synthetic ? '합성 예제: 원본 URL 없음' : '원본 URL 없음 · 출처 ID와 원본 ID로 확인하세요.'}</p>}</article>;
}
export function PurchaseDetail({ selected, mode }) {
  const [state, setState] = useState({ loading: true });
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
  if (state.loading || state.error) return <div id="purchase-detail"><h2 id="purchase-title">구매 상세</h2><p role="status">{state.error ? '상세를 불러오지 못했습니다. 닫은 뒤 다시 시도하세요.' : '상세를 불러오는 중입니다…'}</p></div>;
  const a = state.analysis, t = a.target, market = a.comparison_type === 'market';
  const strict = mode !== 'api' || a.status === 'comparable';
  const reference = strict ? { ...a, reasons: a.reasons, limitations: a.limitations } : preliminary.data;
  const display = reference ? { ...a, reference_unit_price: reference.reference_unit_price, difference: reference.difference, difference_pct: reference.difference_pct } : a;
  const included = (value) => value === true ? '포함' : value === false ? '미포함' : '확인 불가';
  return <div id="purchase-detail"><p className="detail-eyebrow">{a.synthetic ? '화면 개발용 합성 예제' : '실제 공개 구매 자료'}</p><h2 id="purchase-title">{t.item_name}</h2><p className="detail-description">{[agencyName(t.agency_name), t.model, t.purchased_at].filter(Boolean).join(' · ')}</p>
    <section className="detail-section"><h3>단가 비교 요약 <span className="status">{strict ? '비교 결과' : '조건 미확인 참고'}</span></h3>
      {!strict && preliminary.loading ? <p role="status">참고 가격을 불러오는 중입니다…</p> : !strict && preliminary.error ? <p>참고 가격을 불러오지 못했습니다.</p> : reference && <>
        <Difference analysis={display} preliminary={!strict} emptyLabel="비교 자료 부족" /><PriceBars analysis={display} />
        {reference.difference != null ? <><p>{market ? '연결된 판매처의 단가 중앙값' : strict ? '다른 기관 구매 단가 중앙값' : '다른 기관별 단가 중앙값의 중앙값'}을 기준으로 비교했어요. 구매 단가 {money(t.unit_price)}에서 기준 단가 {money(reference.reference_unit_price)}를 뺀 차이입니다.</p><p>참고 자료 {reference.comparison_count}건{!strict && !market && <> · 다른 기관 {reference.agency_count}곳 · {reference.comparison_basis === 'same_quantity' ? '같은 수량' : '유사 수량 (0.5~2배)'} · 구매일 차이 180일 이내</>}</p></> : <p>{reference.reasons?.join(' ') || '계산에 필요한 비교 자료가 부족합니다.'}</p>}
        <p>구매 수량 {t.quantity ?? '확인 불가'} {t.unit ?? ''} · 계약 {t.contract_id ?? '확인 불가'}<br />세금 {included(t.tax_included)} · 배송 {included(t.delivery_included)} · 설치 {included(t.installation_included)}</p>
        <ul>{(reference.limitations ?? []).map((text) => <li key={text}>{text}</li>)}</ul>
        {reference.comparison_records?.length > 0 && <details><summary>비교에 사용된 개별 자료와 출처 ({reference.comparison_count}건)</summary>{reference.comparison_records.map((record) => <div key={record.record_id ?? record.market_price_id}><p>단가 {money(record.unit_price ?? record.price)} · {record.purchased_at ?? record.checked_at} · 수량 {record.quantity ?? '확인 불가'} {record.unit}</p><SourceCard record={record} /></div>)}</details>}
      </>}
    </section>
    <section className="detail-section"><h3>구매 기록 출처</h3><SourceCard record={t} /></section>
  </div>;
}
const initialFilters = { q: '', agency_id: '', item_id: '', status: '', comparison_type: 'agency', sort: 'preliminary_available_desc' };
export default function PurchasePreview({ initialAgency = '', defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen), [mode, setMode] = useState('api');
  const [draft, setDraft] = useState(''), [filters, setFilters] = useState({ ...initialFilters, agency_id: initialAgency });
  const [options, setOptions] = useState({ agencies: [], items: [] });
  const [result, setResult] = useState({ items: [], total: 0, synthetic: null });
  const [loading, setLoading] = useState(false), [error, setError] = useState(false), [retry, setRetry] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false), [moreError, setMoreError] = useState(false);
  const sentinel = useRef(null), moreRequest = useRef(null), loadingMoreRef = useRef(false);
  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
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
    if (!open || mode !== 'api') { setSummary(null); return; }
    const controller = new AbortController();
    setSummary(null);
    getApi(`/preliminary-summary?comparison_type=${filters.comparison_type}`, AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]))
      .then((data) => { if (!controller.signal.aborted) setSummary(data); })
      .catch(() => { if (!controller.signal.aborted) setSummary({ error: true }); });
    return () => controller.abort();
  }, [open, mode, filters.comparison_type]);
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
  const change = (key, value) => { setSelected(null); setFilters((current) => ({ ...current, [key]: value, ...(key === 'item_id' && !value && current.sort === 'difference_pct_desc' ? { sort: 'preliminary_available_desc' } : {}) })); };
  const dates = result.items.map((a) => a.target.retrieved_at).filter(Boolean).sort();
  return <details className="purchase-preview section" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}><summary>구매 내역 조회 <span>실제 자료 / 합성 예제</span></summary><div className="preview-content">
    <p className="preview-notice">{result.synthetic === true ? '화면 개발용 합성 예제입니다. 실제 구매나 분석 결과가 아닙니다.' : result.synthetic === false ? '실제 구매 자료의 참고 가격 차이입니다. 계약 상태와 세금·배송·설치 등 조건은 확인되지 않았으며 가격 차이만으로 이상 거래를 판단할 수 없습니다.' : '자료를 불러와 실제 또는 합성 여부를 확인합니다.'}</p>
    {mode === 'api' && <p className="preview-meta" role="status">{summary?.error ? '전체 참고 비교 건수를 불러오지 못했습니다.' : summary ? `전체 구매 ${summary.total.toLocaleString()}건 중 ${summary.comparison_type === 'agency' ? '기관 간' : '시중가'} 참고 비교 가능 ${summary.available.toLocaleString()}건 (검색·필터 적용 전)` : '전체 참고 비교 건수를 확인하는 중입니다…'}</p>}
    <form className="purchase-search" onSubmit={(event) => { event.preventDefault(); change('q', draft.trim()); }}><label htmlFor="purchase-query">구매 검색</label><div><input id="purchase-query" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={200} placeholder="기관·물품·모델명" /><button type="submit" className="outline-button">검색</button></div></form>
    <div className="purchase-filters">{!initialAgency && <label>데이터 연결<select value={mode} onChange={(event) => { setSelected(null); setMode(event.target.value); }}><option value="api">실제 구매 자료 API</option><option value="local">정적 합성 예제 (서버 없이)</option></select></label>}
      <label>기관<select disabled={!!initialAgency} value={filters.agency_id} onChange={(event) => change('agency_id', event.target.value)}><option value="">전체 기관</option>{options.agencies.map((o) => <option key={o.id} value={o.id}>{agencyName(o.name)}</option>)}</select></label>
      <label>품목<select value={filters.item_id} onChange={(event) => change('item_id', event.target.value)}><option value="">전체 품목</option>{options.items.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>엄격 비교 상태<select value={filters.status} onChange={(event) => change('status', event.target.value)}><option value="">전체 상태</option>{Object.entries(statusLabels).map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
      <label>비교 유형<select value={filters.comparison_type} onChange={(event) => change('comparison_type', event.target.value)}><option value="agency">기관 간</option><option value="market">시중가</option></select></label>
      <label>정렬<select value={filters.sort} onChange={(event) => change('sort', event.target.value)}><option value="preliminary_available_desc">참고 비교 가능 우선</option><option value="purchased_desc">구매일 최신순</option><option value="difference_pct_desc" disabled={!filters.item_id}>엄격 비교 차이율 순 (품목 선택 필요)</option></select></label></div>
    <p className="preview-meta">검색어: {filters.q || '전체'} · 기관: {agencyName(options.agencies.find((o) => o.id === filters.agency_id)?.name) ?? '전체'} · 품목: {options.items.find((o) => o.id === filters.item_id)?.name ?? '전체'} · 상태: {statusLabels[filters.status] ?? '전체'} · 비교: {filters.comparison_type === 'agency' ? '기관 간' : '시중가'} · {mode === 'api' ? 'API 조회' : '정적 예제 내 조회'}</p>
    {!loading && !error && <p className="preview-meta">검색 결과 {result.total}건 · 자료 수집 시각(표기된 날짜) {dates.at(-1)?.slice(0, 10) ?? '해당 없음'} · {result.synthetic === false ? '원본 자료 범위' : '예제 비교 기간'} {[...new Set(result.items.map((a) => `${a.comparison_period.from} ~ ${a.comparison_period.to}`))].join(', ') || '해당 없음'}</p>}
    <div role="status" aria-live="polite" id="preview-feedback">{loading ? '불러오는 중입니다…' : error ? <>조회하지 못했습니다. API 서버를 실행하거나 정적 합성 예제로 전환하세요. <button className="outline-button" onClick={() => setRetry((value) => value + 1)}>다시 시도</button></> : !result.items.length ? '검색 결과가 없습니다. 조건을 바꿔보세요.' : ''}</div>
    <div className="purchase-grid">{result.items.map((a) => {
      const reference = mode === 'api' ? referenceResults[`${a.comparison_type}:${a.record_id}`] : null;
      const useReference = a.status !== 'comparable' && reference && !reference.error;
      const display = useReference ? { ...a, reference_unit_price: reference.reference_unit_price, difference: reference.difference, difference_pct: reference.difference_pct } : a;
      const label = mode !== 'api' || a.status === 'comparable' ? statusLabels[a.status] : !reference ? '참고 가격 확인 중' : reference.error ? '참고 가격 조회 실패' : reference.difference == null ? '참고 자료 부족' : (reference.comparison_basis === 'same_quantity' ? '같은 수량 참고 비교' : reference.comparison_basis === 'similar_quantity' ? '유사 수량 참고 비교' : '조건 미확인 참고 비교');
      return <article className="purchase-card" key={`${a.record_id}-${a.comparison_type}`}><div className="purchase-top"><span className="status">{label}</span><time>{a.target.purchased_at}</time></div><div className="purchase-icon" aria-hidden="true">▤</div><h3>{a.target.item_name}</h3><p className="purchase-spec">{[a.target.model, a.target.specification].filter(Boolean).join(' · ')}</p><p className="purchase-agency">{agencyName(a.target.agency_name)}</p><Difference analysis={display} preliminary={useReference} emptyLabel={mode === 'api' && a.status !== 'comparable' ? label : undefined} /><PriceBars analysis={display} /><div className="purchase-bottom"><span>{useReference ? `참고 ${reference.comparison_count}건 · 조건 확인 필요` : `비교 ${a.comparison_count}건 · 근거 ${a.evidence_ids.length}건`}</span><button onClick={() => setSelected(a)} aria-label={`${agencyName(a.target.agency_name)} ${a.target.item_name} 자세히 보기`}>자세히 보기 ↗</button></div></article>;
    })}</div>
    {mode === 'api' && result.items.length > 0 && result.items.length < result.total && <div ref={sentinel} role="status" aria-live="polite"><p>{loadingMore ? '다음 구매 기록을 불러오는 중입니다…' : moreError ? '다음 구매 기록을 불러오지 못했습니다.' : `${result.total}건 중 ${result.items.length}건 표시`}</p><button className="outline-button" onClick={loadMore} disabled={loadingMore}>{moreError ? '다시 시도' : '더 보기'}</button></div>}
    {selected && <Drawer title={selected.synthetic ? "합성 구매 예제 상세" : "구매 상세"} labelledBy="purchase-title" onClose={() => setSelected(null)}><PurchaseDetail selected={selected} mode={mode} /></Drawer>}
  </div></details>;
}
