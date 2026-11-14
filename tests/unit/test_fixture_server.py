"""Verify real demo data lookup, contract shape, and safe unavailable comparison."""
import asyncio
import json
import sys
import tempfile
import unittest
from decimal import Decimal
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
        self.assertEqual(listing['total'], 47795)
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

    def test_display_name_alias_search_preserves_original_agency(self):
        status, result = request('/api/purchases', {'q': '전남광주특별시', 'page_size': '1'})
        self.assertEqual(status, 200)
        self.assertGreater(result['total'], 0)
        self.assertEqual(result['items'][0]['target']['agency_name'], '전남광주통합특별시 무안청사')

    def test_muan_scope_combines_original_codes_without_changing_records(self):
        _, options = request('/api/options')
        muan = [item for item in options['agencies'] if item['name'] == '전남광주특별시']
        self.assertEqual(len(muan), 1)
        scope_id = muan[0]['id']
        _, scope = request('/api/purchases', {'agency_id': scope_id})
        _, first = request('/api/purchases', {'agency_id': '6460000'})
        _, second = request('/api/purchases', {'agency_id': '6130769'})
        self.assertEqual(scope['total'], first['total'] + second['total'])
        self.assertGreater(first['total'], 0)
        self.assertGreater(second['total'], 0)
        self.assertTrue(all(item['target']['agency_id'] in ('6460000', '6130769') for item in scope['items']))
        _, filtered = request('/api/purchases', {'agency_id': scope_id, 'q': '노트북'})
        self.assertTrue(all('노트북' in (item['target']['item_name'] + (item['target']['model'] or '')) for item in filtered['items']))

    def test_filters_dates_pagination_and_market(self):
        _, first = request('/api/purchases', {'page': '1', 'page_size': '2'})
        _, page = request('/api/purchases', {'page': '2', 'page_size': '2'})
        self.assertEqual((page['total'], len(page['items'])), (47795, 2))
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
        from budget_transparency.api.server import _explanation_cache
        _explanation_cache.clear()
        with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=fake):
            request('/api/purchases/' + item['record_id'])
            fake.assert_not_called()
            _, default = request('/api/explanations/' + item['record_id'])
            self.assertEqual(default['mode'], 'fallback')
            fake.assert_not_called()
            status, body = request('/api/explanations/' + item['record_id'], {'ai': '1'})
            _, cached = request('/api/explanations/' + item['record_id'], {'ai': '1'})
            self.assertEqual(cached, body)
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
                status, body = request('/api/explanations/' + record_id, {'comparison_type': 'market', 'ai': '1'})
            self.assertEqual(status, 200)
            validate('explanation', body)
            self.assertEqual((body['mode'], body['comparison_type']), ('fallback', 'market'))
        with patch('budget_transparency.api.server.gemini.make_generate') as make:
            self.assertEqual(request('/api/explanations/missing')[0], 404)
            make.assert_not_called()

    def test_preliminary_explanation_matches_reference_and_keeps_limits(self):
        record_id = 'pps:6410000:R25TB01196089/00/1'
        _, reference = request('/api/preliminary/' + record_id, {'comparison_type': 'market'})
        self.assertIsNotNone(reference['difference'])
        _, result = request('/api/explanations/' + record_id, {'comparison_type': 'market'})
        self.assertEqual(result['mode'], 'fallback')
        self.assertIn('참고 기준', result['summary'])
        self.assertNotIn('계산하지 않았', result['summary'])
        self.assertTrue(any('조건' in text for text in result['cautions']))
        self.assertEqual(result['evidence_ids'], [record_id])
        fake = unittest.mock.Mock(return_value=json.dumps({'evidence_ids': [record_id], 'caution_ids': ['market']}))
        from budget_transparency.api.server import _explanation_cache
        _explanation_cache.clear()
        with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=fake):
            _, ai = request('/api/explanations/' + record_id, {'comparison_type': 'market', 'ai': '1'})
        self.assertEqual(ai['mode'], 'ai')
        self.assertIn('참고 기준', ai['summary'])
        self.assertIn('판매 조건', ' '.join(ai['cautions']))
        user_prompt = fake.call_args.args[1]
        self.assertIn('조건 미확인 참고 비교', user_prompt)
        self.assertNotIn(reference['difference'], user_prompt)

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
        for kind in ('agency', 'market'):
            record_id = 'pps:6410000:R26TB01752652/00/3' if kind == 'agency' else 'pps:6410000:R25TB01196089/00/1'
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

    def test_same_item_group_enables_reference_when_model_is_missing(self):
        record_id = 'pps:6410000:R26TB01752652/00/3'
        _, detail = request('/api/purchases/' + record_id)
        self.assertIsNone(detail['target']['model'])
        status, result = request('/api/preliminary/' + record_id, {'comparison_type': 'agency'})
        self.assertEqual(status, 200)
        self.assertEqual((result['reference_unit_price'], result['difference'], result['comparison_count']), ('25000', '0', 7))
        self.assertTrue(all(r['agency_id'] != detail['target']['agency_id'] for r in result['comparison_records']))
        self.assertTrue(all(Decimal(r['quantity']) == Decimal(detail['target']['quantity']) for r in result['comparison_records']))
        self.assertTrue(any('모델명과 계약 조건은 미확인' in text for text in result['limitations']))
        _, batch = request('/api/preliminary', {'record_id': record_id, 'comparison_type': 'agency'})
        self.assertEqual(batch['items'][0]['difference'], result['difference'])
        self.assertEqual(detail['status'], 'unavailable')

    def test_fewer_than_three_same_quantity_records_are_not_ranked(self):
        record_id = 'pps:6410000:R25TB01196089/00/1'
        _, result = request('/api/preliminary/' + record_id, {'comparison_type': 'agency'})
        self.assertLess(result['comparison_count'], 3)
        self.assertIsNone(result['reference_unit_price'])
        self.assertIsNone(result['difference_pct'])
        self.assertTrue(any('최소 5건' in reason for reason in result['reasons']))

    def test_older_records_and_cross_period_peers_are_available(self):
        record_id = 'pps:6410000:R25TB00939963/00/2'
        status, detail = request('/api/purchases/' + record_id)
        self.assertEqual(status, 200)
        self.assertEqual(detail['target']['purchased_at'], '2025-08-28')
        _, comparison = request('/api/preliminary/' + record_id, {'comparison_type': 'agency'})
        self.assertIsNotNone(comparison['difference_pct'])
        self.assertTrue(any(row['purchased_at'] >= '2025-11-14' for row in comparison['comparison_records']))
        self.assertEqual(request('/api/purchases', {'date_from': '2024-11-14', 'date_to': '2025-11-13', 'page_size': '1'})[1]['total'], 20327)

    def test_reference_requires_diverse_agencies_and_uses_agency_medians(self):
        from budget_transparency.analysis.preliminary import preliminary
        base = {'item_id': 'item', 'model': 'model', 'specification': 'spec', 'unit': '개', 'currency': 'KRW', 'status': 'unknown', 'purchased_at': '2026-06-01'}
        target = {**base, 'record_id': 'a', 'agency_id': 'A', 'quantity': '1', 'unit_price': '150'}
        peers = [{**base, 'record_id': name, 'agency_id': agency, 'quantity': quantity, 'unit_price': amount}
                 for name, agency, quantity, amount in [('b', 'B', '1.0', '100'), ('c', 'B', '1', '120'), ('d', 'B', '1', '140'), ('e', 'C', '1', '130'), ('f', 'D', '1', '160')]]
        group = ('item', 'model', 'spec', '개', 'KRW')
        with patch('budget_transparency.analysis.preliminary._load', return_value=({'a': target}, {}, {}, {group: [target, *peers[:4]]}, {})):
            insufficient = preliminary('a', 'agency')
        self.assertEqual((insufficient['comparison_count'], insufficient['agency_count']), (4, 2))
        self.assertIsNone(insufficient['difference_pct'])
        with patch('budget_transparency.analysis.preliminary._load', return_value=({'a': target}, {}, {}, {group: [target, *peers]}, {})):
            result = preliminary('a', 'agency')
        self.assertEqual((result['comparison_count'], result['agency_count'], result['comparison_basis']), (5, 3, 'same_quantity'))
        self.assertEqual((result['reference_unit_price'], result['difference_pct']), ('130', '15.38'))
        peers[4]['quantity'] = '2'
        with patch('budget_transparency.analysis.preliminary._load', return_value=({'a': target}, {}, {}, {group: [target, *peers]}, {})):
            result = preliminary('a', 'agency')
        self.assertEqual(result['comparison_basis'], 'similar_quantity')
        peers[4]['purchased_at'] = '2025-01-01'
        with patch('budget_transparency.analysis.preliminary._load', return_value=({'a': target}, {}, {}, {group: [target, *peers]}, {})):
            result = preliminary('a', 'agency')
        self.assertIsNone(result['difference_pct'])

    def test_city_records_and_missing_previous_year_are_distinguished(self):
        _, listing = request('/api/purchases', {'agency_id': '6110000', 'page_size': '1'})
        self.assertEqual(listing['total'], 1533)
        self.assertEqual(listing['items'][0]['target']['agency_name'], '서울특별시')
        _, dist = request('/api/region-distribution', {'agency_id': '6110000'})
        self.assertEqual(dist['total'], 1533)
        monthly = dist['monthly_purchases']
        self.assertIsNone(monthly['months'][0]['count'])
        november = next(row for row in monthly['months'] if row['month'] == '2025-11')
        self.assertTrue(november['partial'])
        self.assertIsNotNone(november['count'])
        self.assertEqual(monthly['coverage_from'], '2025-11-14')

    def test_inconsistent_shared_group_is_reported_as_server_error(self):
        from budget_transparency.analysis.preliminary import PreliminaryDataError
        with patch('budget_transparency.api.server.preliminary', side_effect=PreliminaryDataError):
            status, body = request('/api/preliminary/example')
        self.assertEqual(status, 500)
        validate('error', body)

    def test_reference_ranking_excludes_null_and_matches_detail(self):
        status, first = request('/api/preliminary-rankings', {'page_size': '2'})
        self.assertEqual(status, 200)
        self.assertEqual(first['total'] + first['excluded_count'], 47795)
        self.assertTrue(all(item['difference_pct'] is not None for item in first['items']))
        self.assertGreaterEqual(Decimal(first['items'][0]['difference_pct']), Decimal(first['items'][1]['difference_pct']))
        _, second = request('/api/preliminary-rankings', {'page': '2', 'page_size': '2'})
        self.assertGreaterEqual(Decimal(first['items'][-1]['difference_pct']), Decimal(second['items'][0]['difference_pct']))
        self.assertTrue(set(x['record_id'] for x in first['items']).isdisjoint(x['record_id'] for x in second['items']))
        item = first['items'][0]
        _, detail = request('/api/preliminary/' + item['record_id'])
        self.assertEqual((item['difference_pct'], item['reference_unit_price'], item['comparison_count']),
                         (detail['difference_pct'], detail['reference_unit_price'], detail['comparison_count']))
        self.assertEqual(request('/api/preliminary-rankings', {'page_size': '101'})[0], 400)

    def test_reference_summary_and_availability_sort(self):
        _, summary = request('/api/preliminary-summary', {'comparison_type': 'agency'})
        self.assertEqual(summary['total'], 47795)
        self.assertEqual(summary['available'] + summary['unavailable'], summary['total'])
        _, ranking = request('/api/preliminary-rankings', {'page_size': '1'})
        self.assertEqual(summary['available'], ranking['total'])
        _, listing = request('/api/purchases', {'sort': 'preliminary_available_desc', 'page_size': '3'})
        self.assertEqual(listing['total'], 47795)
        for item in listing['items']:
            _, reference = request('/api/preliminary/' + item['record_id'])
            self.assertIsNotNone(reference['difference_pct'])
        _, market_summary = request('/api/preliminary-summary', {'comparison_type': 'market'})
        self.assertEqual(market_summary['total'], 47795)
        self.assertEqual(market_summary['available'] + market_summary['unavailable'], 47795)
        self.assertEqual(request('/api/preliminary-summary', {'comparison_type': 'invalid'})[0], 400)

    def test_region_distribution_uses_same_scope_and_excludes_missing_values(self):
        for agency in ('6410000', 'scope:jeonnam-gwangju-muan', 'missing'):
            _, distribution = request('/api/region-distribution', {'agency_id': agency})
            _, purchases = request('/api/purchases', {'agency_id': agency, 'page_size': '1'})
            self.assertEqual(distribution['total'], purchases['total'])
            self.assertEqual(distribution['compared'] + distribution['excluded'], distribution['total'])
            self.assertEqual(distribution['higher'] + distribution['equal'] + distribution['lower'], distribution['compared'])
            monthly = distribution['monthly_purchases']
            self.assertEqual(sum(m['count'] for m in monthly['months']), monthly['dated_total'])
            self.assertEqual(monthly['dated_total'] + monthly['excluded'], distribution['total'])
            self.assertEqual((monthly['months'][0]['month'], monthly['months'][-1]['month']), ('2024-11', '2026-11'))
            self.assertTrue(monthly['months'][0]['partial'])
            self.assertTrue(monthly['months'][-1]['partial'])
        _, total = request('/api/region-distribution')
        _, ranking = request('/api/preliminary-rankings', {'page_size': '1'})
        self.assertEqual(total['compared'], ranking['total'])

    def test_region_comparison_uses_each_region_as_its_own_denominator(self):
        status, comparison = request('/api/region-comparison')
        self.assertEqual(status, 200)
        self.assertEqual(len(comparison['items']), 12)
        for region in comparison['items']:
            _, detail = request('/api/region-distribution', {'agency_id': region['agency_id']})
            self.assertEqual((region['total'], region['compared'], region['higher']),
                             (detail['total'], detail['compared'], detail['higher']))
            self.assertLessEqual(region['higher'], region['compared'])

    def test_region_report_is_grounded_and_ai_is_requested_explicitly(self):
        from budget_transparency.api.server import _explanation_cache
        _explanation_cache.clear()
        fake = unittest.mock.Mock(return_value=json.dumps({'check_ids': ['peak', 'price']}))
        with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=fake):
            status, basic = request('/api/region-report', {'agency_id': '6410000'})
            self.assertEqual((status, basic['mode']), (200, 'fallback'))
            fake.assert_not_called()
            _, ai = request('/api/region-report', {'agency_id': '6410000', 'ai': '1'})
            _, cached = request('/api/region-report', {'agency_id': '6410000', 'ai': '1'})
        self.assertEqual(ai['mode'], 'ai')
        self.assertEqual(ai['paragraphs'], basic['paragraphs'])
        self.assertEqual(ai, cached)
        fake.assert_called_once()
        self.assertIn('품목', ai['checks'][0])
        self.assertTrue(any('지급' in text for text in ai['limitations']))
        self.assertNotIn('unit_price', fake.call_args.args[1])
        self.assertEqual(request('/api/region-report', {'agency_id': 'missing'})[0], 404)

    def test_region_report_rejects_unknown_ai_text(self):
        fake = unittest.mock.Mock(return_value=json.dumps({'check_ids': ['unknown'], 'text': '추측 문장'}))
        with patch('budget_transparency.api.server.gemini.load_env'), patch('budget_transparency.api.server.gemini.make_generate', return_value=fake):
            _, result = request('/api/region-report', {'agency_id': '6530000', 'ai': '1'})
        self.assertEqual(result['mode'], 'fallback')
        self.assertNotIn('추측 문장', str(result))

if __name__ == '__main__':
    unittest.main()
