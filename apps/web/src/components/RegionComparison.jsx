import { useEffect, useState } from 'react';
import { getApi } from './PurchasePreview.jsx';

export default function RegionComparison({ selectedId }) {
  const [state, setState] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    getApi('/region-comparison', AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]))
      .then((data) => { if (!controller.signal.aborted) setState({ data }); })
      .catch(() => { if (!controller.signal.aborted) setState({ error: true }); });
    return () => controller.abort();
  }, [retry]);
  const data = state.data;
  return <section className="region-chart region-overview" aria-labelledby="region-comparison-title">
    <div className="region-chart-heading"><div><h3 id="region-comparison-title">지역별 참고 기준보다 높은 구매 비율</h3><p>기관 간 참고 비교가 계산된 구매를 기준으로 지역별 비율을 비교합니다.</p></div><span className="region-chart-tag">조건 미확인 참고</span></div>
    {state.loading ? <p className="region-chart-feedback" role="status">그래프를 불러오는 중입니다…</p> : state.error ? <p className="region-chart-feedback" role="status">그래프를 불러오지 못했습니다. <button className="outline-button" onClick={() => setRetry((n) => n + 1)}>다시 시도</button></p> : <>
      <div className="region-line-wrap"><svg className="region-line-chart" style={{ minWidth: `${Math.max(960, 110 + data.items.length * 102)}px` }} viewBox={`0 0 ${Math.max(960, 110 + data.items.length * 102)} 300`} role="img" aria-label="지역별 참고 기준보다 높은 구매 비율 꺾은선 그래프">
        {[0, 25, 50, 75, 100].map((value) => <g key={value}><line x1="55" x2={Math.max(925, 80 + (data.items.length - 1) * 102)} y1={240 - value * 1.9} y2={240 - value * 1.9} className="line-grid" /><text x="45" y={244 - value * 1.9} textAnchor="end" className="line-axis">{value}%</text></g>)}
        {data.items.map((item, index, items) => {
          if (!index || !item.compared || !items[index - 1].compared) return null;
          const previous = items[index - 1];
          return <line key={`line-${item.agency_id}`} x1={80 + (index - 1) * 102} y1={240 - previous.higher / previous.compared * 190} x2={80 + index * 102} y2={240 - item.higher / item.compared * 190} className="line-stroke" />;
        })}
        {data.items.map((item, index) => {
          const x = 80 + index * 102, pct = item.compared ? item.higher / item.compared * 100 : null;
          return <g key={item.agency_id}><text x={x} y="269" textAnchor="middle" className={item.agency_id === selectedId ? 'line-axis selected' : 'line-axis'}>{item.name}</text>{pct !== null && <><circle cx={x} cy={240 - pct * 1.9} r={item.agency_id === selectedId ? 7 : 5} className={item.agency_id === selectedId ? 'line-point selected' : 'line-point'}><title>{item.name}: {item.higher} / {item.compared}건 ({pct.toFixed(1)}%)</title></circle><text x={x} y={226 - pct * 1.9} textAnchor="middle" className="line-value">{pct.toFixed(1)}%</text></>}</g>;
        })}
      </svg></div>
      <details className="chart-details"><summary>지역별 비교 건수와 기준 보기</summary><div className="region-line-values">{data.items.map((item) => <span key={item.agency_id} className={item.agency_id === selectedId ? 'selected' : ''}>{item.name} {item.compared ? `${item.higher}/${item.compared}건` : '계산 불가'}</span>)}</div>
      <p className="region-chart-note">각 기관의 참고 비교가 계산된 구매 건수 중 기준보다 높은 건수의 비율입니다. 기관별 수집 기간·표본 크기와 품목 구성이 다르며, 서울·부산·대전은 2025-11-14부터 수집했습니다. 선은 지역 비교를 돕기 위한 연결선이지 시간 추세가 아닙니다.</p>
      <p className="region-chart-note">대상 기간 {data.period.from} ~ {data.period.to} · 구매일 180일 이내 다른 기관 3곳·5건 이상. 계약 상태와 비용 조건은 미확인일 수 있으며 이 그래프는 이상 거래나 기관 평가가 아닙니다.</p></details>
    </>}
  </section>;
}
