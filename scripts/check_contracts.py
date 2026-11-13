"""Validate v1 fixture schemas and cross-record calculation invariants."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import json
import sys
from statistics import median
try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    sys.exit('Install tooling: python3 -m pip install -r requirements-dev.txt')
ROOT = Path(__file__).resolve().parents[1]
F = ROOT / 'tests/fixtures/contracts-v1'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def require(ok, message):
    if not ok: raise ValueError(message)
def validate_analysis(a):
    require(a['record_id'] == a['target']['record_id'], 'target ID mismatch')
    require(a['comparison_count'] == len(a['comparison_records']), 'count mismatch')
    require(a['synthetic'] == a['target']['synthetic'], 'synthetic mismatch')
    peers = a['comparison_records']
    key = 'record_id' if a['comparison_type'] == 'agency' else 'market_price_id'
    expected_ids = [a['record_id']] + [r[key] for r in peers]
    require(a['evidence_ids'] == expected_ids, 'evidence IDs mismatch')
    require(len(expected_ids) == len(set(expected_ids)), 'duplicate IDs')
    if a['comparison_type'] == 'agency':
        require(a['agency_count'] == len({r['agency_id'] for r in peers}), 'agency count mismatch')
    else: require(a['agency_count'] is None, 'market agency count must be null')
    if a['status'] != 'comparable':
        require(all(a[k] is None for k in ('reference_unit_price','difference','difference_pct')), 'invalid comparison has numbers')
        require(bool(a['reasons']), 'missing reason')
        return
    require(bool(peers), 'empty comparison')
    for r in peers:
        for k in ('item_id','model','specification','unit','currency','tax_included','delivery_included','installation_included'):
            require(r[k] is not None and r[k] == a['target'][k], f'incompatible {k}')
        require(r['synthetic'] == a['synthetic'], 'mixed synthetic/real')
        if a['comparison_type'] == 'agency':
            require(r['agency_id'] != a['target']['agency_id'], 'same agency included')
            require(r['quantity'] == a['target']['quantity'], 'quantity mismatch')
    price_key = 'unit_price' if a['comparison_type'] == 'agency' else 'price'
    ref = median([Decimal(r[price_key]) for r in peers])
    diff = Decimal(a['target']['unit_price']) - ref
    require(ref > 0, 'nonpositive reference')
    require(Decimal(a['reference_unit_price']) == ref, 'wrong reference')
    require(Decimal(a['difference']) == diff, 'wrong difference')
    require(Decimal(a['difference_pct']) == (diff/ref*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP), 'wrong percentage')
def main():
    manifest = read(F/'manifest.json')
    for file, schema_file in manifest.items():
        schema = read(ROOT/'docs/contracts'/schema_file)
        Draft202012Validator.check_schema(schema)
        value = read(F/file)
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(value)
        if schema_file == 'analysis.schema.json': validate_analysis(value)
    purchases = read(F/'purchases.json')
    require(len({r['record_id'] for r in purchases}) == len(purchases), 'duplicate purchase IDs')
    a = read(F/'analysis.json'); e = read(F/'explanation.json')
    require(set(e['evidence_ids']) <= set(a['evidence_ids']), 'unknown explanation evidence')
    for k in ('dataset_version','record_id','comparison_type'): require(e[k] == a[k], 'explanation mismatch')
    print(f'Contract v1: {len(manifest)} fixtures passed schema and applicable semantic checks')
if __name__ == '__main__': main()
