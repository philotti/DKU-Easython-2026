import { useEffect, useState } from 'react';
import { getApi } from './PurchasePreview.jsx';

function Evidence({ data, label }) {
  if (!data) return null;
  return <details className="region-report-limits"><summary>{label} ({data.count.toLocaleString()}건 중 최대 {data.records.length}건)</summary><p>같은 품목명은 서로 다른 규격을 포함할 수 있습니다. 아래 식별자로 원본을 확인하세요.</p><ul>{data.records.map((record) => <li key={record.record_id}>원본 ID: {record.source_record_id ?? record.record_id} · 수량 {record.quantity ?? '확인 불가'} {record.unit ?? ''} · 단가 {record.unit_price == null ? '확인 불가' : `${record.unit_price}원`} {record.source_id === 'pps-15129471-item' ? <a href="https://www.data.go.kr/data/15129471/openapi.do" target="_blank" rel="noopener noreferrer">자료 출처 ↗</a> : record.source_id === 'pps-15129427-goods-detail' ? <a href="https://www.data.go.kr/data/15129427/openapi.do" target="_blank" rel="noopener noreferrer">자료 출처 ↗</a> : <span>출처 ID: {record.source_id ?? '확인 불가'}</span>}</li>)}</ul></details>;
}

export function CitizenNextSteps() {
  return <section className="citizen-next-steps" aria-labelledby="citizen-next-steps-title">
    <h4 id="citizen-next-steps-title">시민이 직접 확인하기</h4>
    <p>구매 목적 등 추가 자료가 필요하다면 정보공개포털에서 정보공개 청구를 검토해 보세요.</p>
    <a href="https://www.open.go.kr/" target="_blank" rel="noopener noreferrer">정보공개포털 열기 ↗</a>
  </section>;
}

export function PriceExamples({ items }) {
  if (!items?.length) return null;
  const amount = (value) => `${Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}원`;
  return <div className="region-price-examples"><strong>참고 기준보다 높은 사례 · 차이율 순 최대 3건</strong><p>비용 조건이 확인되지 않은 참고 비교입니다. 차이가 크다는 것만으로 구매에 문제가 있다고 판단할 수 없습니다.</p><ul>{items.map((item) => <li key={item.record_id}>
    <strong>{item.item_name}</strong><span>{item.purchased_at} · 구매 단가 {amount(item.unit_price)} / 참고 단가 {amount(item.reference_unit_price)} ({item.unit ?? '단위 미확인'})</span><span>비교 {item.comparison_count}건 / {item.agency_count}개 기관</span><span>원본 식별자: {item.source_record_id ?? '확인 불가'} · 출처 ID: {item.source_id ?? '확인 불가'}</span>
  </li>)}</ul><p>상세 비교와 근거는 아래 구매 내역에서 확인할 수 있습니다.</p></div>;
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
      <p className="region-report-period">분석 기간: {data.period.from} ~ {data.period.to} · 구매 품목 행 기준</p>
      {data.signal_count > 0 && <div className="region-report-signal"><strong>추가 확인 사례 {data.signal_count.toLocaleString()}개</strong><p>같은 날짜·품목 기록이 기준보다 많은 사례입니다. 잘못된 거래로 판정한 결과는 아닙니다.</p></div>}
      {(data.sections ?? [{ title: '구매 기록 요약', paragraphs: data.paragraphs }]).map((section) => <section className="region-report-section" key={section.title}><h4>{section.title}</h4>{section.paragraphs.map((text) => <p className="region-report-text" key={text}>{text}</p>)}{section.title === '참고 단가 비교' && <PriceExamples items={data.price_examples} />}</section>)}
      {data.comparison_answers?.length > 0 && <section className="region-report-section"><h4>그 외에 참고할 내용</h4><p className="region-report-text">{data.concentration_evidence ? '위 추가 확인 사례' : '위 날짜·품목 최다 사례'}의 전체 기록을 대조했습니다.</p>{data.comparison_answers.map((text) => <p className="region-report-text" key={text}>{text}</p>)}</section>}
      <div className="region-report-checks"><strong>{data.mode === 'ai' ? 'AI가 고른 확인 질문' : '확인해 볼 질문'}</strong><p>구매 원인을 판단한 결과가 아니라, 자료를 살펴볼 때 참고할 질문입니다.</p><ul>{data.checks.map((text) => <li key={text}>{text}</li>)}</ul></div>
      {aiRequests > 0 && data.mode !== 'ai' && <p role="status" className="region-chart-feedback">AI 응답을 사용하지 못해 기본 확인 사항을 표시합니다. 연결 상태와 한도를 확인한 뒤 15초 후 다시 시도해 주세요.</p>}
      <Evidence data={data.daily_evidence} label="날짜·품목 기록 근거 보기" />
      {data.concentration_evidence && (data.concentration_evidence.date !== data.daily_evidence?.date || data.concentration_evidence.item_name !== data.daily_evidence?.item_name) && <Evidence data={data.concentration_evidence} label="추가 확인 사례 근거 보기" />}
      <CitizenNextSteps />
      <details className="region-report-limits"><summary>자료의 한계와 기준</summary><ul>{data.limitations.map((text) => <li key={text}>{text}</li>)}</ul><p>자료 수집 기간: {data.coverage_from} ~ {data.period.to}</p><p>AI는 정해진 확인 사항을 선별하며 수치나 원인을 생성하지 않습니다.</p></details>
    </>}
    {!state.loading && data?.mode !== 'ai' && <button className="outline-button region-report-button" onClick={() => setAiRequests((n) => n + 1)}>{aiRequests ? 'AI 확인 사항 다시 요청' : 'AI로 확인 사항 정리'}</button>}
    <p className="region-chart-note">구매 기록 건수는 실제 지출액이 아닙니다.</p>
  </section>;
}
