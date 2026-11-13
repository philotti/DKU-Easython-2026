"""Check registered demo JSON; absence is allowed during scaffolding."""
import argparse
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {'purchases.json': 'purchases', 'market-prices.json': 'market-prices', 'comparison-policy.json': 'policy'}

def validate_file(path, schema_name):
    value = json.loads(path.read_text(encoding='utf-8'))
    schema = json.loads((ROOT/'docs/contracts'/f'{schema_name}.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    if schema_name == 'policy':
        for key in ('agency_period', 'market_period'):
            if value[key]['from'] > value[key]['to']:
                raise ValueError(f'{key}: start is after end')
        return
    key = 'record_id' if schema_name == 'purchases' else 'market_price_id'
    ids = [r[key] for r in value]
    if len(ids) != len(set(ids)):
        raise ValueError(f'duplicate {key}')
    if len({r['synthetic'] for r in value}) > 1:
        raise ValueError('mixed real and synthetic records')
    for r in value:
        if r['synthetic'] and r['source_url'] is not None:
            raise ValueError('synthetic records must not contain source URLs')
        if not r['synthetic']:
            if not r['source_id']:
                raise ValueError('real records require source_id')
            if schema_name == 'purchases' and not (r['source_record_id'] or r['source_url']):
                raise ValueError('real purchase requires source_record_id or source_url')
            if schema_name == 'market-prices' and not r['source_url']:
                raise ValueError('real market price requires source_url')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path)
    parser.add_argument('--schema', choices=('purchases','market-prices','policy'))
    args = parser.parse_args()
    if bool(args.file) != bool(args.schema):
        parser.error('--file and --schema must be used together')
    if args.file:
        validate_file(args.file, args.schema)
        print(f'OK: {args.file}')
        return
    paths = sorted((ROOT/'data/demo').rglob('*.json'))
    allowed = {ROOT/'data/demo'/name: schema for name,schema in SCHEMAS.items()}
    for path in paths:
        if path not in allowed:
            raise ValueError(f'Unregistered demo JSON: {path.relative_to(ROOT)}; agree a schema before adding it')
        validate_file(path, allowed[path])
        print(f'OK: {path.relative_to(ROOT)}')
    print(f'Demo data: {len(paths)} files checked' if paths else 'Demo data: no files yet (not a completed data validation)')
if __name__ == '__main__':
    main()
