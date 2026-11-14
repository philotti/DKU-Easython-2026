"""Verify real demo data lookup, contract shape, and safe unavailable comparison."""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from budget_transparency.api.server import app


def request(path, params=None):
    messages = []
    query = urlencode(params or {}).encode()
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


def validate(schema, value):
    doc = json.loads((ROOT / 'docs/contracts' / (schema + '.schema.json')).read_text())
    Draft202012Validator(doc, format_checker=FormatChecker()).validate(value)


class PurchaseApiTests(unittest.TestCase):
    def test_real_list_and_detail_match_schema_and_unavailable(self):
        status, listing = request('/api/purchases')
        self.assertEqual(status, 200)
        validate('list', listing)
        self.assertFalse(listing['synthetic'])
        self.assertEqual(listing['total'], 18)
        item = listing['items'][0]
        self.assertEqual(item['status'], 'unavailable')
        self.assertIsNone(item['difference'])
        status, detail = request('/api/purchases/' + item['record_id'])
        self.assertEqual(status, 200)
        validate('analysis', detail)
        self.assertEqual(item, detail)
        self.assertEqual(detail['policy_id'], 'not-configured')

    def test_search_and_agency_together(self):
        status, result = request('/api/purchases', {'agency_id': '6410000', 'q': '노트북'})
        self.assertEqual(status, 200)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['target']['agency_name'], '경기도')
        self.assertIn('노트북', result['items'][0]['target']['item_name'])
        _, empty = request('/api/purchases', {'agency_id': '6410000', 'q': '존재하지않는물품'})
        self.assertEqual((empty['total'], empty['items']), (0, []))

    def test_filters_dates_pagination_and_market(self):
        _, page = request('/api/purchases', {'page': '2', 'page_size': '2'})
        self.assertEqual((page['total'], len(page['items'])), (18, 2))
        _, result = request('/api/purchases', {'date_from': '2026-01-01', 'date_to': '2026-02-01', 'comparison_type': 'market'})
        self.assertTrue(result['items'])
        self.assertTrue(all('2026-01-01' <= x['target']['purchased_at'] <= '2026-02-01' for x in result['items']))
        self.assertIsNone(result['items'][0]['agency_count'])
        validate('list', result)

    def test_invalid_and_not_found(self):
        for params in ({'page_size': '101'}, {'date_from': '2026-02-30'},
                       {'date_from': '2026-03-01', 'date_to': '2026-01-01'},
                       {'sort': 'difference_pct_desc'}, {'comparison_type': 'other'}, {'bogus': 'x'}):
            with self.subTest(params=params):
                status, body = request('/api/purchases', params)
                self.assertEqual(status, 400)
                validate('error', body)
        status, body = request('/api/purchases/missing')
        self.assertEqual(status, 404)
        validate('error', body)

    def test_options(self):
        status, body = request('/api/options')
        self.assertEqual(status, 200)
        validate('options', body)
        self.assertIn('6410000', [a['id'] for a in body['agencies']])

if __name__ == '__main__':
    unittest.main()
