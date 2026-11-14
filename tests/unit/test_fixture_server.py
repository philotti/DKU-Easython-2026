"""Check the fixture API without starting a network server."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from budget_transparency.api.server import app  # noqa: E402


def request(path, query=b''):
    messages = []
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
             'query_string': query, 'headers': [], 'client': ('127.0.0.1', 12345),
             'server': ('127.0.0.1', 8000), 'root_path': ''}
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        messages.append(message)
    asyncio.run(app(scope, receive, send))
    status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
    body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
    return status, json.loads(body)


class FixtureServerTests(unittest.TestCase):
    def test_list_matches_detail(self):
        status, listing = request('/api/purchases')
        self.assertEqual(status, 200)
        self.assertTrue(listing['synthetic'])
        self.assertEqual(listing['total'], 3)
        status, detail = request('/api/purchases/demo-A')
        self.assertEqual(status, 200)
        self.assertEqual(next(a for a in listing['items'] if a['record_id'] == 'demo-A'), detail)
        self.assertEqual(detail['difference'], '30000')
        self.assertEqual(detail['difference_pct'], '25.00')

    def test_unknown_and_invalid_queries(self):
        status, body = request('/api/purchases/missing')
        self.assertEqual((status, body['error']['code']), (404, 'NOT_FOUND'))
        status, body = request('/api/purchases', b'unknown=test')
        self.assertEqual((status, body['error']['code']), (400, 'INVALID_REQUEST'))

    def test_search_filters_and_market_detail(self):
        from urllib.parse import urlencode
        for params, total in [({'q': 'DEMO-100'}, 2),
                              ({'q': 'missing'}, 0),
                              ({'agency_id': 'agency-A', 'status': 'comparable'}, 1),
                              ({'status': 'conditions_unknown'}, 1),
                              ({'comparison_type': 'market'}, 1)]:
            status, body = request('/api/purchases', urlencode(params).encode())
            self.assertEqual(status, 200)
            self.assertEqual(body['total'], total, params)
            for analysis in body['items']:
                _, detail = request('/api/purchases/' + analysis['record_id'], urlencode({'comparison_type': analysis['comparison_type']}).encode())
                self.assertEqual(analysis, detail)
        _, market = request('/api/purchases/demo-A', b'comparison_type=market')
        self.assertEqual(market['reference_unit_price'], '110000')
        self.assertEqual(market['comparison_records'][0]['seller_name'], '가상 판매처')

    def test_pagination_sort_validation_and_unchanged_comparison(self):
        _, listing = request('/api/purchases', b'item_id=demo-item-1&sort=difference_pct_desc')
        self.assertEqual(listing['items'][0]['record_id'], 'demo-A')
        self.assertEqual(listing['items'][-1]['difference_pct'], None)
        _, page = request('/api/purchases', b'page=2&page_size=1')
        self.assertEqual((page['total'], len(page['items'])), (3, 1))
        _, filtered = request('/api/purchases', b'agency_id=agency-A')
        self.assertEqual(filtered['items'][0]['comparison_count'], 3)
        for query in (b'sort=difference_pct_desc', b'comparison_type=other', b'status=bad', b'page=0', b'page_size=101', b'q=a&q=b', b'date_from=2026-99-99', b'date_from=2026-11-14&date_to=2026-11-01'):
            status, _ = request('/api/purchases', query)
            self.assertEqual(status, 400, query)

    def test_options(self):
        status, body = request('/api/options')
        self.assertEqual(status, 200)
        self.assertEqual(body['agencies'][0]['id'], 'agency-A')


if __name__ == '__main__':
    unittest.main()
