import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from budget_transparency.ai.region_report import region_facts, region_report


class RegionReportTests(unittest.TestCase):
    def test_daily_evidence_uses_source_rows_and_is_not_sent_to_model(self):
        distribution = {'compared': 0, 'higher': 0, 'excluded': 3, 'monthly_purchases': {
            'period': {'from': '2025-01-01', 'to': '2025-12-31'}, 'coverage_from': '2025-01-01',
            'dated_total': 3, 'excluded': 0, 'months': [{'month': '2025-03', 'count': 3, 'partial': False}]}}
        records = [{'record_id': f'id-{i}', 'purchased_at': '2025-03-05', 'item_name': '책상',
                    'source_id': 'pps-15129471-item', 'source_record_id': str(i), 'unit_price': '123456', 'unit': '개', 'quantity': '1'} for i in range(3)]
        facts = region_facts('기관', distribution, records)
        observed = {}
        def fake(system, user):
            observed['prompt'] = user
            return json.dumps({'check_ids': ['batch']})
        report = region_report(facts, fake)
        self.assertEqual((report['daily_evidence']['date'], report['daily_evidence']['count']), ('2025-03-05', 3))
        self.assertEqual(len(report['daily_evidence']['records']), 3)
        self.assertIn('2025-03-05', ' '.join(report['paragraphs']))
        self.assertIn('여러 품목 행일 수', report['checks'][0])
        self.assertNotIn('123456', observed['prompt'])
        self.assertEqual(report['mode'], 'ai')
        self.assertEqual([section['title'] for section in report['sections']],
                         ['지역 구매 요약', '날짜·품목 살펴보기', '참고 단가 비교'])
        self.assertEqual([text for section in report['sections'] for text in section['paragraphs']], report['paragraphs'])
        fallback = region_report(facts)
        self.assertIn('계약·납품요구 식별자', fallback['checks'][0])
        self.assertIn('임시 기준에 해당하는', ' '.join(fallback['paragraphs']))
        self.assertNotIn('단가 차이', ' '.join(fallback['checks']))

    def test_partial_month_does_not_become_monthly_peak(self):
        distribution = {'compared': 0, 'higher': 0, 'excluded': 0, 'monthly_purchases': {
            'period': {'from': '2025-01-15', 'to': '2025-02-28'}, 'coverage_from': '2025-01-15',
            'dated_total': 101, 'excluded': 0, 'months': [{'month': '2025-01', 'count': 100, 'partial': True}, {'month': '2025-02', 'count': 1, 'partial': False}]}}
        facts = region_facts('기관', distribution)
        self.assertEqual(facts['peak_months'][0]['month'], '2025-02')
        self.assertIsNone(facts['daily_peak'])

    def test_concentration_requires_repeat_history_and_never_claims_corruption(self):
        distribution = {'compared': 0, 'higher': 0, 'excluded': 0, 'monthly_purchases': {
            'period': {'from': '2025-01-01', 'to': '2025-12-31'}, 'coverage_from': '2025-01-01',
            'dated_total': 17, 'excluded': 0, 'months': [{'month': '2025-03', 'count': 17, 'partial': False}]}}
        records = [{'record_id': f'id-{day}-{i}', 'purchased_at': f'2025-03-{day:02d}', 'item_name': '책상',
                    'source_id': 'pps-15129471-item', 'source_record_id': f'{day}-{i}', 'unit_price': '123456', 'unit': '개', 'quantity': '1'}
                   for day in range(1, 7) for i in range(12 if day == 6 else 1)]
        facts = region_facts('기관', distribution, records)
        report = region_report(facts, lambda *_: json.dumps({'check_ids': ['concentration']}))
        self.assertEqual((report['concentration_evidence']['date'], report['concentration_evidence']['count']), ('2025-03-06', 12))
        self.assertEqual(report['concentration_evidence']['baseline_median'], 1)
        self.assertEqual(report['concentration_evidence']['active_days'], 6)
        self.assertEqual(report['signal_count'], 1)
        self.assertIn('12건', report['comparison_answers'][0])
        self.assertIn('식별자가 없는 기록은 12건', report['comparison_answers'][0])
        self.assertIn('세금 12건', report['comparison_answers'][2])
        self.assertIn('추가 확인', ' '.join(report['paragraphs']))
        self.assertIn('하루 중앙값 1건의 12배', ' '.join(report['paragraphs']))
        self.assertIn('의심스럽다면', ' '.join(report['paragraphs']))
        self.assertIn('원본 식별자와 자료 출처를 직접 확인해 보세요', ' '.join(report['paragraphs']))
        fewer = region_facts('기관', distribution, [r for r in records if r['purchased_at'] != '2025-03-01'])
        self.assertIsNone(fewer['concentration'])
        self.assertEqual(region_report(fewer)['signal_count'], 0)

if __name__ == '__main__':
    unittest.main()
