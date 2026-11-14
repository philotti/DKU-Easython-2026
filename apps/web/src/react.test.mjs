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
