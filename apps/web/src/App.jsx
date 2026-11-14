import { useState } from 'react';
import Drawer from './components/Drawer.jsx';
import PurchasePreview from './components/PurchasePreview.jsx';
import { agencies } from './provinces.js';

function ProvinceDetail({ agency }) {
  return <div id="detail"><p className="detail-eyebrow">도청별 상세 근거</p><h2 id="drawer-title">{agency.name}</h2><p className="detail-description">계약 분석 결과와 판단에 사용된 자료를 확인하는 화면입니다.</p><span className="status">분석 대기</span><div className="detail-stats">{['분석 순위', '분석 점수', '분석 계약 수'].map((text) => <div key={text}><span>{text}</span><strong>—</strong></div>)}</div><section className="detail-section"><h3>분석 개요</h3><dl>{['분석 기간', '비교 대상', '이상치 판정 기준', '점수 산정 방식'].map((text) => <div className="definition-row" key={text}><dt>{text}</dt><dd>기준 확정 후 제공</dd></div>)}</dl></section><section className="detail-section"><h3>이상치 계약 내역</h3><div className="detail-placeholder"><strong>계약 분석 결과를 기다리고 있습니다.</strong><p>품목·계약일·구매 단가·비교 기준과 차이를 여기에 표시합니다.</p></div></section><section className="detail-section"><h3>상세 근거</h3>{['비교에 사용한 계약', '분석 대상에서 제외한 계약과 사유', '원본 출처 및 수집일'].map((text) => <div className="evidence-row" key={text}><span>{text}</span><span>자료 연결 전</span></div>)}</section><p className="detail-footnote">현재는 화면 구조만 제공됩니다. 이 도청의 실제 계약 내역이나 분석 결과가 아닙니다.</p></div>;
}

export default function App() {
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [method, setMethod] = useState(false);
  const visible = filter === 'complete' ? [] : agencies;
  return <>
    <header className="header"><a className="brand" href="#">세금탐지기<span className="brand-subtitle">-도청감지</span></a><nav aria-label="주요 메뉴"><a href="#agencies">도청 목록</a><a href="#ranking">분석 순위</a><a href="#sources">자료 출처</a></nav><span className="header-status"><i />분석 준비 중</span></header>
    <main>
      <section id="agencies" className="section"><div className="section-heading"><h1>도청 목록</h1><span className="subtle">가나다순</span></div><div className="agency-grid">{agencies.map((agency) => <button className="agency-card" key={agency.key} onClick={() => setSelected(agency)}><span className="region">{agency.region}</span><span className="agency-info"><strong>{agency.name}</strong><span>분석 대기</span></span><span className="arrow" aria-hidden="true">↗</span></button>)}</div></section>
      <section id="ranking" className="section"><div className="section-heading"><div><h2>분석 순위</h2><p>분석 결과에 따른 도청별 순위와 계약 현황입니다.</p></div><button className="outline-button" onClick={() => setMethod(true)}>분석 기준 안내</button></div>
        <aside className="jamie-summary" aria-labelledby="jamie-title"><div className="jamie-profile"><div><span className="jamie-role">순위 해설</span><h3 id="jamie-title">제이미의 한눈 요약</h3></div></div><div className="jamie-message"><p className="jamie-greeting">어느 도청을 먼저 살펴보면 될까요?</p><p>아직 분석 결과를 기다리고 있어요. 결과가 준비되면 순위의 주요 변화와 확인할 계약, 비교할 때 주의할 점을 짚어드릴게요.</p><span className="jamie-state">요약 준비 중</span></div></aside>
        <div className="ranking-panel"><div className="toolbar"><div className="tabs" role="group" aria-label="분석 상태">{[['all', '전체 도청'], ['complete', '분석 완료'], ['pending', '분석 대기']].map(([value, text]) => <button key={value} className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{text} <span>{value === 'complete' ? 0 : agencies.length}</span></button>)}</div><span className="subtle">기준 확정 후 순위 제공</span></div><div className="table-scroll"><table><caption className="sr-only">도청별 분석 순위. 분석 전 가나다순 표시.</caption><thead><tr>{['순위', '도청', '분석 계약 수', '이상치 계약 수', '분석 점수', '상태', '상세'].map((text) => <th key={text} scope="col">{text}</th>)}</tr></thead><tbody>{visible.map((agency) => <tr key={agency.key}><td>—</td><th scope="row">{agency.name}</th><td>—</td><td>—</td><td>—</td><td><span className="status">분석 대기</span></td><td><button className="row-link" onClick={() => setSelected(agency)} aria-label={`${agency.name} 상세 보기`}>상세 보기 ↗</button></td></tr>)}</tbody></table></div>{!visible.length && <p className="empty">아직 분석이 완료된 도청이 없습니다.</p>}<div className="table-note">현재 도청명 가나다순입니다. 순위·점수·계약 건수는 분석 결과를 받은 뒤 제공됩니다.</div></div>
      </section>
      <section id="sources" className="section"><div className="section-heading"><div><h2>자료 출처</h2><p>분석에 사용한 원본 자료와 수집 정보를 확인할 수 있습니다.</p></div><span className="subtle">자료 등록 대기</span></div><div className="ranking-panel"><div className="table-scroll"><table><thead><tr>{['자료명', '제공 기관', '대상 기간', '수집일', '이용 조건', '원본'].map((text) => <th key={text}>{text}</th>)}</tr></thead><tbody><tr><td colSpan="6"><p className="empty">아직 등록된 자료 출처가 없습니다.<br />자료가 연결되면 제공 기관과 원본 링크를 함께 표시합니다.</p></td></tr></tbody></table></div><div className="table-note">출처가 확인된 자료만 등록합니다. 개별 계약의 원본과 비교 근거는 도청 상세에 연결할 예정입니다.</div></div></section>
      <PurchasePreview />
      <footer><span>세금탐지기-도청감지</span><p>이상치 분석은 추가 검토 대상을 찾기 위한 정보이며, 위법이나 예산 낭비를 의미하지 않습니다.</p></footer>
    </main>
    {selected && <Drawer title="도청 상세" labelledBy="drawer-title" onClose={() => setSelected(null)}><ProvinceDetail agency={selected} /></Drawer>}
    {method && <Drawer title="분석 기준" labelledBy="method-title" onClose={() => setMethod(false)}><p className="detail-eyebrow">분석 기준</p><h2 id="method-title">분석 기준 안내</h2><p className="detail-description">비교 기준은 담당 팀원과 확정 중입니다.</p><ul className="method-list">{['분석 대상 계약과 기간', '같은 품목의 비교 조건과 최소 표본', '이상치 판정 방법과 기준값', '점수 집계·순위 산정 방식', '제외한 자료와 분석의 한계'].map((text) => <li key={text}>{text}</li>)}</ul></Drawer>}
  </>;
}
