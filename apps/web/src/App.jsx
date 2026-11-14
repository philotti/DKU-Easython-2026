import ProvinceMap from './components/ProvinceMap.jsx';

export default function App() {
  return <>
    <header className="header"><a className="brand" href="#" aria-label="재정돋보기 홈"><svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true"><circle cx="17" cy="17" r="11.5" fill="none" stroke="currentColor" strokeWidth="3.2"/><path d="M25.5 25.5 34 34" fill="none" stroke="currentColor" strokeWidth="3.6" strokeLinecap="round"/><path d="m10.5 13 2.6 8 3.9-7 3.9 7 2.6-8M11.4 17h11.2" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg><span className="brand-name">재정돋보기</span></a><nav aria-label="주요 메뉴"><a href="#agencies">지역별 내역</a><a href="#sources">자료 출처</a></nav></header>
    <main>
      <ProvinceMap />
      <section id="sources" className="section"><div className="section-heading"><div><h2>자료 출처</h2><p>구매 자료와 참고 시중가의 출처를 확인할 수 있습니다.</p></div></div><div className="ranking-panel"><div className="table-scroll"><table><thead><tr>{['자료명', '제공 기관', '대상 기간 / 확인일', '수집일', '원본'].map((text) => <th key={text} scope="col">{text}</th>)}</tr></thead><tbody><tr><td>나라장터쇼핑몰 품목정보</td><td>조달청</td><td>2024-11-14 ~ 2026-11-13</td><td>2026-11-14</td><td><a href="https://www.data.go.kr/data/15129471/openapi.do" target="_blank" rel="noopener noreferrer">공공데이터포털 ↗</a></td></tr><tr><td>나라장터 계약정보</td><td>조달청</td><td>2025-11-14 ~ 2026-11-13</td><td>2026-11-14</td><td><a href="https://www.data.go.kr/data/15129427/openapi.do" target="_blank" rel="noopener noreferrer">공공데이터포털 ↗</a></td></tr><tr><td>시중가 참고 자료</td><td>개별 판매처</td><td>판매 페이지별 확인일</td><td>구매 상세에 표시</td><td>각 구매 상세의 참고 자료에서 확인</td></tr></tbody></table></div><div className="table-note">광역자치단체 본청의 공개 구매 자료를 사용합니다. 개별 구매 원본의 직접 링크가 없는 경우 상세에 출처 ID와 원본 ID를 표시합니다. 시중가는 각 판매처의 확인일 기준이며 구매일 당시 가격과 다를 수 있습니다.</div></div></section>
      <footer><span>재정돋보기</span><p>이상치 분석은 추가 검토 대상을 찾기 위한 정보이며, 위법이나 예산 낭비를 의미하지 않습니다.</p></footer>
    </main>
  </>;
}
