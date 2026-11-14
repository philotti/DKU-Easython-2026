"""Verify real demo data lookup, contract shape, and safe unavailable comparison."""
import asyncio
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
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
        self.assertEqual(listing['total'], 22987)
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
        self.assertGreater(result['total'], 0)
        self.assertTrue(all(x['target']['agency_name'] == '경기도' for x in result['items']))
        self.assertTrue(all('노트북' in x['target']['item_name'] for x in result['items']))
        _, empty = request('/api/purchases', {'agency_id': '6410000', 'q': '존재하지않는물품'})
        self.assertEqual((empty['total'], empty['items']), (0, []))

    def test_filters_dates_pagination_and_market(self):
        _, first = request('/api/purchases', {'page': '1', 'page_size': '2'})
        _, page = request('/api/purchases', {'page': '2', 'page_size': '2'})
        self.assertEqual((page['total'], len(page['items'])), (22987, 2))
        self.assertTrue(set(x['record_id'] for x in first['items']).isdisjoint(x['record_id'] for x in page['items']))
        self.assertGreaterEqual(first['items'][-1]['target']['purchased_at'], page['items'][0]['target']['purchased_at'])
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

    def test_explanation_uses_model_only_on_explanation_request(self):
        _, listing = request('/api/purchases', {'page_size': '1'})
        item = listing['items'][0]
        fake = unittest.mock.Mock(return_value=json.dumps({'evidence_ids': [item['record_id']], 'caution_ids': ['tax']}))
        with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=fake):
            request('/api/purchases/' + item['record_id'])
            fake.assert_not_called()
            status, body = request('/api/explanations/' + item['record_id'])
        self.assertEqual(status, 200)
        validate('explanation', body)
        self.assertEqual(body['mode'], 'ai')
        self.assertIn('세금 포함 여부를 확인하세요.', body['cautions'])
        fake.assert_called_once()

    def test_explanation_falls_back_without_key_or_on_model_failure(self):
        _, listing = request('/api/purchases', {'page_size': '1'})
        record_id = listing['items'][0]['record_id']
        for generator in (None, unittest.mock.Mock(side_effect=RuntimeError('model failure'))):
            with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=generator):
                status, body = request('/api/explanations/' + record_id, {'comparison_type': 'market'})
            self.assertEqual(status, 200)
            validate('explanation', body)
            self.assertEqual((body['mode'], body['comparison_type']), ('fallback', 'market'))
        with patch('budget_transparency.api.server.gemini.make_generate') as make:
            self.assertEqual(request('/api/explanations/missing')[0], 404)
            make.assert_not_called()

    def test_configured_comparison_uses_full_dataset_for_filtered_list_and_detail(self):
        fixtures = ROOT / 'tests/fixtures/contracts-v1'
        purchases = json.loads((fixtures / 'purchases.json').read_text())
        market = json.loads((fixtures / 'market-prices.json').read_text())
        for row in purchases + market:
            row['synthetic'] = False
        policy = json.loads((fixtures / 'policy.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            market_path, policy_path = Path(directory) / 'market.json', Path(directory) / 'policy.json'
            market_path.write_text(json.dumps(market))
            policy_path.write_text(json.dumps(policy))
            with patch('budget_transparency.api.server.load_data', return_value=(purchases, 'test-version')), \
                 patch('budget_transparency.api.server.MARKET_FILE', market_path), \
                 patch('budget_transparency.api.server.POLICY_FILE', policy_path):
                status, listing = request('/api/purchases', {'agency_id': 'agency-A', 'item_id': 'demo-item-1', 'status': 'comparable', 'sort': 'difference_pct_desc'})
                self.assertEqual(status, 200)
                self.assertEqual(listing['total'], 1)
                analysis = listing['items'][0]
                self.assertEqual((analysis['difference'], analysis['difference_pct']), ('30000', '25.00'))
                self.assertEqual(analysis['comparison_count'], 3)
                self.assertEqual(request('/api/purchases/demo-A')[1], analysis)
                _, market_result = request('/api/purchases/demo-A', {'comparison_type': 'market'})
                self.assertEqual((market_result['difference'], market_result['difference_pct']), ('40000', '36.36'))
                with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=None):
                    _, explanation = request('/api/explanations/demo-A')
                self.assertEqual(explanation['dataset_version'], analysis['dataset_version'])
                self.assertEqual(explanation['evidence_ids'], analysis['evidence_ids'])

    def test_invalid_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / 'policy.json'
            policy_path.write_text('{}')
            with patch('budget_transparency.api.server.POLICY_FILE', policy_path):
                status, body = request('/api/purchases')
        self.assertEqual(status, 500)
        validate('error', body)

    def test_actual_unknown_status_remains_unavailable_with_test_policy(self):
        policy = json.loads((ROOT / 'tests/fixtures/contracts-v1/policy.json').read_text())
        policy['agency_period'] = {'from': '2025-11-14', 'to': '2026-11-13'}
        policy['market_period'] = {'from': '2026-11-14', 'to': '2026-11-14'}
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / 'policy.json'
            policy_path.write_text(json.dumps(policy))
            with patch('budget_transparency.api.server.POLICY_FILE', policy_path):
                status, listing = request('/api/purchases', {'page_size': '1'})
        self.assertEqual(status, 200)
        result = listing['items'][0]
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['difference'])
        self.assertTrue(any('active' in reason for reason in result['reasons']))

    def test_real_preliminary_prices_are_labeled_and_evidence_is_available(self):
        record_id = 'pps:6410000:R25TB01196089/00/1'
        for kind in ('agency', 'market'):
            status, result = request('/api/preliminary/' + record_id, {'comparison_type': kind})
            self.assertEqual(status, 200)
            self.assertEqual(result['label'], '조건 미확인 참고 비교')
            self.assertGreater(result['comparison_count'], 0)
            self.assertIsNotNone(result['difference'])
            self.assertTrue(result['limitations'])
            self.assertEqual(result['comparison_count'], len(result['comparison_records']))
            if kind == 'market':
                self.assertEqual((result['reference_unit_price'], result['difference']), ('796500', '-147500'))
                self.assertTrue(all(r['source_url'] for r in result['comparison_records']))
        self.assertEqual(request('/api/preliminary/missing')[0], 404)

    def test_preliminary_batch_matches_detail_without_evidence_payload(self):
        record_id = 'pps:6410000:R25TB01196089/00/1'
        status, batch = request('/api/preliminary', {'record_id': record_id, 'comparison_type': 'market'})
        self.assertEqual(status, 200)
        _, detail = request('/api/preliminary/' + record_id, {'comparison_type': 'market'})
        self.assertEqual(batch['items'][0]['difference'], detail['difference'])
        self.assertEqual(batch['items'][0]['comparison_count'], len(detail['comparison_records']))
        self.assertNotIn('comparison_records', batch['items'][0])
        self.assertEqual(request('/api/preliminary')[0], 400)
        self.assertEqual(request('/api/preliminary', {'record_id': record_id, 'bogus': 'x'})[0], 400)

if __name__ == '__main__':
    unittest.main()
