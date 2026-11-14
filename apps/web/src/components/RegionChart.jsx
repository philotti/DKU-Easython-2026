import { useEffect, useState } from 'react';
import { getApi } from './PurchasePreview.jsx';

export default function RegionChart({ agencyId, name }) {
  const [state, setState] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ agency_id: agencyId });
    setState({ loading: true });
    getApi(`/region-distribution?${params}`, AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]))
      .then((data) => { if (!controller.signal.aborted) setState({ data }); })
      .catch(() => { if (!controller.signal.aborted) setState({ error: true }); });
    return () => controller.abort();
  }, [agencyId, retry]);
  const monthly = state.data?.monthly_purchases;
  const shares = monthly?.months.map((month) => month.count === null ? null : monthly.dated_total ? month.count / monthly.dated_total * 100 : 0) ?? [];
  const max = Math.max(5, Math.ceil(Math.max(...shares.filter((value) => value !== null), 0) / 5) * 5);
  const chartWidth = Math.max(960, 110 + (monthly?.months.length ?? 0) * 70);
  const position = (index) => ({ x: 65 + index * 70, y: 235 - shares[index] / max * 180 });
  return <section className="region-chart" aria-labelledby="monthly-chart-title">
    <div className="region-chart-heading"><div><h3 id="monthly-chart-title">{name} 월별 구매 기록 비율</h3><p>날짜가 확인된 구매 품목 기록에서 각 월이 차지하는 비율입니다.</p></div><span className="region-chart-tag">구매 건수 기준</span></div>
    {state.loading ? <p className="region-chart-feedback" role="status">그래프를 불러오는 중입니다…</p> : state.error ? <p className="region-chart-feedback" role="status">그래프를 불러오지 못했습니다. <button className="outline-button" onClick={() => setRetry((n) => n + 1)}>다시 시도</button></p> : <>
      <div className="region-line-wrap"><svg className="region-line-chart" style={{ minWidth: `${chartWidth}px` }} viewBox={`0 0 ${chartWidth} 300`} role="img" aria-label={`${name} 월별 구매 기록 비율 꺾은선 그래프`}>
        {[0, .25, .5, .75, 1].map((step) => <g key={step}><line x1="55" x2={chartWidth - 30} y1={235 - step * 180} y2={235 - step * 180} className="line-grid" /><text x="46" y={239 - step * 180} textAnchor="end" className="line-axis">{(max * step).toFixed(1)}%</text></g>)}
        {monthly.months.map((month, index) => index && shares[index] !== null && shares[index - 1] !== null ? <line key={`line-${month.month}`} x1={position(index - 1).x} y1={position(index - 1).y} x2={position(index).x} y2={position(index).y} className="line-stroke" /> : null)}
        {monthly.months.map((month, index) => { const { x, y } = position(index); return <g key={month.month}>{shares[index] !== null && <><circle cx={x} cy={y} r="5" className="line-point"><title>{month.month}: {month.count}건 ({shares[index].toFixed(1)}%)</title></circle><text x={x} y={y - 13} textAnchor="middle" className="line-value">{shares[index].toFixed(1)}%</text></>}<text x={x} y="262" textAnchor="middle" className="line-axis">{month.month.slice(2)}{month.partial ? '*' : ''}</text></g>; })}
      </svg></div>
      {!monthly.dated_total && <p className="region-chart-feedback">이 기간에 날짜가 확인된 구매 기록이 없습니다.</p>}
      <p className="region-chart-note">* 수집 기간의 첫 달과 마지막 달은 일부 기간입니다. 구매 기록 수는 실제 지출액이 아닙니다.</p>
      <details className="chart-details"><summary>월별 건수와 그래프 기준 보기</summary><div className="region-line-values">{monthly.months.map((month, index) => <span key={month.month}>{month.month}{month.partial ? '*' : ''} {month.count === null ? "자료 없음" : `${month.count.toLocaleString()}건 (${shares[index].toFixed(1)}%)`}</span>)}</div>
        <p>비율은 기간 내 날짜가 확인된 구매 품목 기록 {monthly.dated_total.toLocaleString()}건을 기준으로 합니다. 날짜 미확인 또는 범위 밖 {monthly.excluded.toLocaleString()}건은 제외합니다. 세로축은 이 지역의 최대 비율에 맞춰 조정됩니다.</p>
        <p>수집 기간: {monthly.coverage_from} ~ {monthly.period.to}. 수집 전 월은 0건이 아닌 자료 없음이며 2026년 12월 자료는 없습니다. 구매 품목 행의 날짜·건수는 실제 예산 집행액이나 지급액이 아니며, 비중만으로 밀어내기 지출을 판정할 수 없습니다.</p></details>
    </>}
  </section>;
}
