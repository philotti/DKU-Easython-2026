import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from jsonschema import ValidationError
ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
contracts=load('check_contracts')
data=load('check_data')
class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((ROOT/'tests/fixtures/contracts-v1/purchases.json').read_text())
    def check_rows(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'purchases.json'
            path.write_text(json.dumps(rows))
            data.validate_file(path,'purchases')
    def test_valid_synthetic(self):
        self.check_rows(self.rows)
    def test_wrong_money_type(self):
        self.rows[0]['unit_price']=150000
        with self.assertRaises(ValidationError): self.check_rows(self.rows)
    def test_unknown_field(self):
        self.rows[0]['price']=150000
        with self.assertRaises(ValidationError): self.check_rows(self.rows)
    def test_duplicate_id(self):
        self.rows.append(copy.deepcopy(self.rows[0]))
        with self.assertRaises(ValueError): self.check_rows(self.rows)
    def test_mixed_data(self):
        self.rows[0]['synthetic']=False
        with self.assertRaises(ValueError): self.check_rows(self.rows)
    def test_real_without_provenance(self):
        row=self.rows[0];row['synthetic']=False
        with self.assertRaises(ValueError): self.check_rows([row])
    def test_real_with_provenance(self):
        row=self.rows[0];row.update(synthetic=False,source_id='test-source',source_record_id='test-record')
        self.check_rows([row])
    def test_wrong_calculation_and_evidence(self):
        original=contracts.read(contracts.F/'analysis.json')
        for field,value in [('difference','999'),('evidence_ids',['missing']),('comparison_count',99)]:
            with self.subTest(field=field):
                changed=copy.deepcopy(original);changed[field]=value
                with self.assertRaises(ValueError): contracts.validate_analysis(changed)
    def test_reversed_policy_period(self):
        policy=contracts.read(contracts.F/'policy.json')
        policy['agency_period']['from']='2026-12-01'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'policy.json';path.write_text(json.dumps(policy))
            with self.assertRaises(ValueError): data.validate_file(path,'policy')
if __name__ == '__main__': unittest.main()
