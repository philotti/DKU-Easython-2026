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
        self.assertEqual(listing['total'], 1)
        status, detail = request('/api/purchases/demo-A')
        self.assertEqual(status, 200)
        self.assertEqual(listing['items'][0], detail)
        self.assertEqual(detail['difference'], '30000')
        self.assertEqual(detail['difference_pct'], '25.00')

    def test_unknown_and_unimplemented_queries(self):
        status, body = request('/api/purchases/missing')
        self.assertEqual((status, body['error']['code']), (404, 'NOT_FOUND'))
        status, body = request('/api/purchases', b'q=test')
        self.assertEqual((status, body['error']['code']), (400, 'INVALID_REQUEST'))

    def test_options(self):
        status, body = request('/api/options')
        self.assertEqual(status, 200)
        self.assertEqual(body['agencies'][0]['id'], 'agency-A')


if __name__ == '__main__':
    unittest.main()
