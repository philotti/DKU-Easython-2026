import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';

test('React page renders province directory, ranking, filters and preview', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { default: App } = await server.ssrLoadModule('/src/App.jsx');
    const html = renderToStaticMarkup(createElement(App));
    for (const label of ['세금탐지기', '강원특별자치도청', '경기도청', '자료 출처', '구매 카드 조회', '구매 검색', '데이터 연결']) assert.ok(html.includes(label), label);
    assert.equal((html.match(/class="agency-card"/g) ?? []).length, 9);
    assert.ok(!html.includes('dangerouslySetInnerHTML'));
    assert.ok(!html.includes('제이미의 한눈 요약'));
    assert.ok(!html.includes('jamie-summary'));
    assert.ok(!html.includes('jamie.png'));
  } finally { await server.close(); }
});
