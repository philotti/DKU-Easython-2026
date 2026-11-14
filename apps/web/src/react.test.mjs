import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';

test('React page renders the map, region selectors and sources', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { default: App } = await server.ssrLoadModule('/src/App.jsx');
    const html = renderToStaticMarkup(createElement(App));
    for (const label of ['재정돋보기', '강원특별자치도청', '경기도청', '전남광주특별시', '나라장터쇼핑몰 품목정보', '자료 출처', '2020년 기준', '지도에서 지역을 선택해']) assert.ok(html.includes(label), label);
    assert.equal((html.match(/aria-label="[^"]+ 구매 내역 보기"/g) ?? []).length, 13);
    assert.equal((html.match(/aria-label="전남광주특별시 구매 내역 보기"/g) ?? []).length, 2);
    assert.ok(!html.includes('dangerouslySetInnerHTML'));
    assert.ok(!html.includes('제이미의 한눈 요약'));
    assert.ok(!html.includes('jamie-summary'));
    assert.ok(!html.includes('jamie.png'));
  } finally { await server.close(); }
});

test('regional report begins with a loading state', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { default: RegionReport } = await server.ssrLoadModule('/src/components/RegionReport.jsx');
    const html = renderToStaticMarkup(createElement(RegionReport, { agencyId: '6410000', name: '경기도청' }));
    assert.ok(html.includes('경기도청 구매 기록 요약'));
    assert.ok(html.includes('요약을 불러오는 중'));
  } finally { await server.close(); }
});

test('citizen guidance links to the information disclosure portal', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { CitizenNextSteps } = await server.ssrLoadModule('/src/components/RegionReport.jsx');
    const html = renderToStaticMarkup(createElement(CitizenNextSteps));
    assert.ok(html.includes('정보공개 청구'));
    assert.ok(html.includes('https://www.open.go.kr/'));
    assert.ok(!html.includes('google.com/search'));
  } finally { await server.close(); }
});

test('price examples show reference differences and source identifiers', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { PriceExamples } = await server.ssrLoadModule('/src/components/RegionReport.jsx');
    const html = renderToStaticMarkup(createElement(PriceExamples, { items: [{ record_id: 'r1', item_name: '책상', purchased_at: '2025-01-01', unit_price: '1200', reference_unit_price: '1000', difference_pct: '20', unit: '개', comparison_count: 5, agency_count: 3, source_record_id: '원본-1', source_id: 'source' }] }));
    for (const value of ['책상', '1,200원', '1,000원', '원본-1', '비용 조건이 확인되지 않은']) assert.ok(html.includes(value), value);
    assert.ok(!html.includes('+20%'));
    assert.equal(renderToStaticMarkup(createElement(PriceExamples, { items: [] })), '');
  } finally { await server.close(); }
});
