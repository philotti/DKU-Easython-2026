// Display-only directory. Keys are local UI keys, not backend agency IDs.
// Ranking data will be integrated after the team defines the analysis contract.
export const agencies = [
  { key: 'gangwon', name: '강원특별자치도청', region: '강원' },
  { key: 'gyeonggi', name: '경기도청', region: '경기' },
  { key: 'gyeongnam', name: '경상남도청', region: '경남' },
  { key: 'gyeongbuk', name: '경상북도청', region: '경북' },
  { key: 'jeonnam', name: '전라남도청', region: '전남' },
  { key: 'jeonbuk', name: '전북특별자치도청', region: '전북' },
  { key: 'jeju', name: '제주특별자치도청', region: '제주' },
  { key: 'chungnam', name: '충청남도청', region: '충남' },
  { key: 'chungbuk', name: '충청북도청', region: '충북' },
];
const $ = (id) => document.getElementById(id);
const jamiePhoto = $('jamie-photo');
function revealJamie() {
  if (!jamiePhoto.naturalWidth) return;
  jamiePhoto.hidden = false;
  jamiePhoto.previousElementSibling.hidden = true;
}
jamiePhoto.addEventListener('load', revealJamie);
if (jamiePhoto.complete) revealJamie();
let opener;
let filter = 'all';

function renderRanking() {
  const visible = filter === 'complete' ? [] : agencies;
  $('ranking-body').innerHTML = visible.map((agency) => `<tr><td class="rank">—</td><th scope="row">${agency.name}</th><td>—</td><td>—</td><td>—</td><td><span class="status">분석 대기</span></td><td><button class="row-link" data-agency="${agency.key}" aria-label="${agency.name} 상세 보기">상세 보기 <span aria-hidden="true">↗</span></button></td></tr>`).join('');
  $('empty').hidden = visible.length > 0;
}

function openDialog(content, trigger, label) {
  opener = trigger;
  $('drawer-label').textContent = label;
  $('detail').innerHTML = content;
  $('drawer').showModal();
  $('close').focus();
}

function openAgency(key, trigger) {
  const agency = agencies.find((item) => item.key === key);
  if (!agency) return;
  openDialog(`<p class="detail-eyebrow">도청별 상세 근거</p><h2 id="drawer-title">${agency.name}</h2><p class="detail-description">계약 분석 결과와 판단에 사용된 자료를 확인하는 화면입니다.</p><span class="status">분석 대기</span><div class="detail-stats"><div><span>분석 순위</span><strong>—</strong></div><div><span>분석 점수</span><strong>—</strong></div><div><span>분석 계약 수</span><strong>—</strong></div></div><section class="detail-section"><h3>분석 개요</h3><dl><dt>분석 기간</dt><dd>미정</dd><dt>비교 대상</dt><dd>기준 확정 후 제공</dd><dt>이상치 판정 기준</dt><dd>기준 확정 후 제공</dd><dt>점수 산정 방식</dt><dd>기준 확정 후 제공</dd></dl></section><section class="detail-section"><h3>이상치 계약 내역 <span class="section-count">—</span></h3><div class="detail-placeholder"><span class="placeholder-line" aria-hidden="true"></span><strong>계약 분석 결과를 기다리고 있습니다.</strong><p>품목·계약일·구매 단가·비교 기준과 차이를 여기에 표시합니다.</p></div></section><section class="detail-section"><h3>상세 근거</h3><div class="evidence-row"><span>비교에 사용한 계약</span><span>자료 연결 전</span></div><div class="evidence-row"><span>분석 대상에서 제외한 계약과 사유</span><span>자료 연결 전</span></div><div class="evidence-row"><span>원본 출처 및 수집일</span><span>자료 연결 전</span></div></section><p class="detail-footnote">현재는 화면 구조만 제공됩니다. 이 도청의 실제 계약 내역이나 분석 결과가 아닙니다.</p>`, trigger, '도청 상세');
}

$('all-count').textContent = agencies.length;
$('pending-count').textContent = agencies.length;
$('agency-list').innerHTML = agencies.map((agency) => `<button class="agency-card" data-agency="${agency.key}"><span class="region">${agency.region}</span><span class="agency-info"><strong>${agency.name}</strong><span>분석 대기</span></span><span class="arrow" aria-hidden="true">↗</span></button>`).join('');

for (const id of ['agency-list', 'ranking-body']) $(id).addEventListener('click', (event) => {
  const button = event.target.closest('button[data-agency]');
  if (button) openAgency(button.dataset.agency, button);
});

document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach((tab) => {
    const selected = tab === button;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-pressed', String(selected));
  });
  renderRanking();
}));

$('method').addEventListener('click', (event) => openDialog('<p class="detail-eyebrow">분석 기준</p><h2 id="drawer-title">분석 기준 안내</h2><p class="detail-description">비교 기준은 담당 팀원과 확정 중입니다.</p><section class="detail-section"><h3>확정 후 공개할 내용</h3><ul class="method-list"><li>분석 대상 계약과 기간</li><li>같은 품목으로 비교하는 조건과 최소 표본 수</li><li>이상치 판정 방법과 기준값</li><li>도청별 점수 집계 및 순위 산정 방식</li><li>제외한 자료와 분석의 한계</li></ul></section><p class="detail-footnote">기준과 근거가 준비되기 전에는 순위나 점수를 표시하지 않습니다.</p>', event.currentTarget, '분석 기준'));
$('close').onclick = () => $('drawer').close();
$('drawer').addEventListener('click', (event) => {
  if (event.target !== $('drawer')) return;
  const rect = $('drawer').getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) $('drawer').close();
});
$('drawer').addEventListener('close', () => opener?.focus());
renderRanking();
