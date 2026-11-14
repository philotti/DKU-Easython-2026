import { useEffect, useState } from 'react';
import { getApi } from './PurchasePreview.jsx';

function Evidence({ data, label }) {
  if (!data) return null;
  return <details className="region-report-limits"><summary>{label} ({data.count.toLocaleString()}건 중 최대 {data.records.length}건)</summary><p>같은 품목명은 서로 다른 규격을 포함할 수 있습니다. 아래 식별자로 원본을 확인하세요.</p><ul>{data.records.map((record) => <li key={record.record_id}>원본 ID: {record.source_record_id ?? record.record_id} · 수량 {record.quantity ?? '확인 불가'} {record.unit ?? ''} · 단가 {record.unit_price == null ? '확인 불가' : `${record.unit_price}원`} {record.source_id === 'pps-15129471-item' ? <a href="https://www.data.go.kr/data/15129471/openapi.do" target="_blank" rel="noopener noreferrer">자료 출처 ↗</a> : record.source_id === 'pps-15129427-goods-detail' ? <a href="https://www.data.go.kr/data/15129427/openapi.do" target="_blank" rel="noopener noreferrer">자료 출처 ↗</a> : <span>출처 ID: {record.source_id ?? '확인 불가'}</span>}</li>)}</ul></details>;
}

export default function RegionReport({ agencyId, name }) {
  const [state, setState] = useState({ loading: true });
  const [aiRequests, setAiRequests] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ agency_id: agencyId, ai: aiRequests ? '1' : '0' });
    setState({ loading: true });
    getApi(`/region-report?${params}`, AbortSignal.any([controller.signal, AbortSignal.timeout(aiRequests ? 45000 : 20000)]))
      .then((data) => { if (!controller.signal.aborted) setState({ data }); })
      .catch(() => { if (!controller.signal.aborted) setState({ error: true }); });
    return () => controller.abort();
  }, [agencyId, aiRequests]);
  const data = state.data;
  return <section className="region-report" aria-labelledby="region-report-title">
    <div className="region-report-heading"><div><h3 id="region-report-title">{name} 구매 기록 요약</h3><p>확인된 구매 기록과 참고 단가 비교를 바탕으로 정리합니다.</p></div>{data && <span className="region-chart-tag">{data.mode === 'ai' ? 'AI 확인 사항' : '기본 요약'}</span>}</div>
    {state.loading ? <p role="status" className="region-chart-feedback">{aiRequests ? 'AI 확인 사항을 요청하고 있습니다. 최대 30초 정도 걸릴 수 있습니다…' : '구매 기록 요약을 불러오는 중입니다…'}</p> : state.error ? <p role="status" className="region-chart-feedback">요약을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p> : <>
      {data.paragraphs.map((text) => <p className="region-report-text" key={text}>{text}</p>)}
      <div className="region-report-checks"><strong>{data.mode === 'ai' ? 'AI가 고른 확인 사항·미검증 가설' : '기본 확인 사항'}</strong><ul>{data.checks.map((text) => <li key={text}>{text}</li>)}</ul></div>
      {aiRequests > 0 && data.mode !== 'ai' && <p role="status" className="region-chart-feedback">AI 응답을 사용하지 못해 기본 확인 사항을 표시합니다. 연결 상태와 한도를 확인한 뒤 15초 후 다시 시도해 주세요.</p>}
      <Evidence data={data.daily_evidence} label="날짜·품목 기록 근거 보기" />
      {data.concentration_evidence && (data.concentration_evidence.date !== data.daily_evidence?.date || data.concentration_evidence.item_name !== data.daily_evidence?.item_name) && <Evidence data={data.concentration_evidence} label="추가 확인 사례 근거 보기" />}
      <details className="region-report-limits"><summary>자료의 한계와 기준</summary><ul>{data.limitations.map((text) => <li key={text}>{text}</li>)}</ul><p>자료 수집 기간: {data.coverage_from} ~ {data.period.to}</p><p>AI는 정해진 확인 사항을 선별하며 수치나 원인을 생성하지 않습니다.</p></details>
    </>}
    {!state.loading && data?.mode !== 'ai' && <button className="outline-button region-report-button" onClick={() => setAiRequests((n) => n + 1)}>{aiRequests ? 'AI 확인 사항 다시 요청' : 'AI로 확인 사항 정리'}</button>}
    <p className="region-chart-note">구매 기록 건수는 실제 지출액이 아닙니다.</p>
  </section>;
}
