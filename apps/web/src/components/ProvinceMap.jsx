import { useState } from 'react';
import shapes from '../../assets/map/provinces-2020.json';
import PurchasePreview from './PurchasePreview.jsx';
import RegionChart from './RegionChart.jsx';
import RegionReport from './RegionReport.jsx';
import RegionComparison from './RegionComparison.jsx';
import Drawer from './Drawer.jsx';

const regions = {
  '서울특별시': { name: '서울특별시청', id: '6110000' },
  '부산광역시': { name: '부산광역시청', id: '6260000' },
  '대전광역시': { name: '대전광역시청', id: '6300000' },
  '경기도': { name: '경기도청', id: '6410000' },
  '강원도': { name: '강원특별자치도청', id: '6530000' },
  '충청북도': { name: '충청북도청', id: '6430000' },
  '충청남도': { name: '충청남도청', id: '6440000' },
  '전라북도': { name: '전북특별자치도청', id: '6540000' },
  '전라남도': { name: '전남광주특별시', id: 'scope:jeonnam-gwangju-muan' },
  '광주광역시': { name: '전남광주특별시', id: 'scope:jeonnam-gwangju-muan' },
  '경상북도': { name: '경상북도청', id: '6470000' },
  '경상남도': { name: '경상남도청', id: '6480000' },
  '제주특별자치도': { name: '제주특별자치도청', id: '6500000' },
};
const uniqueRegions = [...new Map(Object.values(regions).map((region) => [region.id, region])).values()];

export default function ProvinceMap() {
  const [selected, setSelected] = useState(null);
  const choose = (region) => setSelected(region);
  return <section id="agencies" className="section">
    <div className="section-heading"><div><h1>지역별 구매 내역</h1><p>지도에서 지역을 선택해 본청의 구매 내역과 참고 차이율을 살펴보세요.</p></div></div>
    <div className="map-layout">
      <div className="map-canvas">
        <svg className="province-map" viewBox="0 0 800 759" role="group" aria-label="대한민국 지역 선택 지도">
          {shapes.map((shape) => {
            const region = regions[shape.name];
            const active = region && selected?.id === region.id;
            return <path key={shape.name} d={shape.d} fillRule={shape.fillRule} className={region ? `map-region${active ? ' selected' : ''}` : 'map-region unavailable'}
              {...(region ? { role: 'button', tabIndex: 0, 'aria-label': `${region.name} 구매 내역 보기`, 'aria-pressed': !!active,
                onClick: () => choose(region), onKeyDown: (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(region); } } } : { 'aria-label': `${shape.name}: 자료 없음` })}><title>{region ? region.name : `${shape.name} · 자료 없음`}</title></path>;
          })}
        </svg>
        <p className="map-caption">지도 경계는 2020년 기준 표시용 자료입니다. 최근 행정구역 변경은 반영되지 않았을 수 있습니다.</p>
      </div>
      <div className="map-guide"><p className="map-kicker">지역 선택</p><h2>어느 지역의<br />구매 내역이 궁금하세요?</h2><p>색이 있는 지역을 누르거나 아래에서 선택해 주세요. 자료는 광역자치단체 본청 구매에 한정됩니다. 서울·부산·대전은 2025년 11월 14일부터 수집했습니다.</p><div className="map-region-buttons">{uniqueRegions.map((region) => <button key={region.id} className={selected?.id === region.id ? 'active' : ''} aria-pressed={selected?.id === region.id} onClick={() => choose(region)}>{region.name}<span aria-hidden="true">↗</span></button>)}</div><p className="map-footnote">전남광주특별시는 무안청사 자료만 포함합니다. 지도에서 광주와 전남은 같은 자료로 연결됩니다. 색이 없는 지역은 현재 연결된 구매 자료가 없습니다.</p></div>
    </div>
    <RegionComparison selectedId={selected?.id} />
    {selected && <Drawer variant="region-modal" title="지역별 구매 내역" labelledBy="region-title" onClose={() => setSelected(null)}><div className="region-drawer"><p className="detail-eyebrow">지역별 구매 현황</p><h2 id="region-title">{selected.name}</h2><p className="detail-description">월별 구매 기록과 참고 비교가 가능한 구매 내역을 확인하세요.</p><RegionChart key={`chart-${selected.id}`} agencyId={selected.id} name={selected.name} /><RegionReport key={`report-${selected.id}`} agencyId={selected.id} name={selected.name} /><PurchasePreview key={selected.id} initialAgency={selected.id} defaultOpen /></div></Drawer>}
    <p className="map-attribution">지도 출처: <a href="https://github.com/swcho/korea-maps" target="_blank" rel="noopener noreferrer">통계청 SGIS 기반 korea-maps (2020)</a></p>
  </section>;
}
