"""Read-only purchase search and policy-controlled price comparison."""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from budget_transparency.ai import gemini
from budget_transparency.ai.explain import explain_analysis
from budget_transparency.analysis.compare import ComparisonEngine, AnalysisConfigurationError
from budget_transparency.analysis.preliminary import preliminary

ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = ROOT / 'data' / 'shared' / 'provinces-20251114-20261113' / 'purchases.json'
MARKET_FILE = DATA_FILE.with_name('market-prices.json')
POLICY_FILE = ROOT / 'data' / 'demo' / 'comparison-policy.json'
PERIOD = {'from': '2025-11-14', 'to': '2026-11-13'}  # source dataset coverage, not a comparison period
class DataError(Exception):
    pass


app = FastAPI(title='공공계약 구매 조회 API', version='0.2.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['GET'], allow_headers=['*'])


def error(status, code, message):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message}})


def load_data():
    try:
        raw = DATA_FILE.read_bytes()
        records = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise DataError from exc
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise DataError('invalid data')
    if any(r.get('synthetic') is not False for r in records):
        raise DataError('unexpected synthetic data')
    ids = [r['record_id'] for r in records]
    if len(ids) != len(set(ids)):
        raise DataError('duplicate record ID')
    return records, 'sha256:' + hashlib.sha256(raw).hexdigest()


def unavailable(record, version, comparison_type):
    return {'contract_version': '1.0', 'dataset_version': version,
            'record_id': record['record_id'], 'comparison_type': comparison_type,
            'synthetic': False, 'status': 'unavailable',
            'reasons': ['실제 비교 정책이 등록되지 않아 분석하지 않았습니다.'],
            'target': record, 'reference_unit_price': None, 'difference': None,
            'difference_pct': None, 'comparison_records': [], 'excluded_records': [],
            'comparison_count': 0, 'agency_count': 0 if comparison_type == 'agency' else None,
            'comparison_period': PERIOD, 'method_version': 'unit-price-v1',
            'policy_id': 'not-configured', 'evidence_ids': [record['record_id']],
            'limitations': ['비교 결과가 아닙니다. 표시된 기간은 원본 자료의 수집 범위입니다.',
                            '계약 상태와 세금·배송·설치 조건은 원본에서 확인되지 않았을 수 있습니다.']}


def comparison_context(records, version):
    """Load a real policy only when explicitly registered; never use the synthetic fixture."""
    if not POLICY_FILE.exists():
        return None, [], version
    try:
        market_raw = MARKET_FILE.read_bytes()
        market = json.loads(market_raw)
        policy_raw = POLICY_FILE.read_bytes()
        policy = json.loads(policy_raw)
        if not isinstance(market, list) or any(not isinstance(r, dict) or r.get('synthetic') is not False for r in market):
            raise DataError('invalid market data')
        market_ids = [r['market_price_id'] for r in market]
        if len(set(market_ids)) != len(market_ids):
            raise DataError('duplicate market ID')
        combined = hashlib.sha256((version + '\n').encode() + market_raw + b'\n' + policy_raw).hexdigest()
        version = 'sha256:' + combined
        return ComparisonEngine(policy, version), market, version
    except (OSError, ValueError, KeyError, TypeError, AnalysisConfigurationError) as exc:
        raise DataError('invalid comparison configuration') from exc


def analyze(record, records, market, version, kind, engine):
    if engine is None:
        return unavailable(record, version, kind)
    try:
        return engine.compare_purchase(record['record_id'], records, market, kind)
    except (ValueError, KeyError, TypeError) as exc:
        raise DataError('invalid comparison input') from exc


def validate_params(request, allowed):
    params = request.query_params
    if set(params) - allowed or any(len(params.getlist(k)) != 1 for k in params):
        raise ValueError('지원하지 않거나 중복된 검색 조건입니다.')
    return params


def parse_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('올바르지 않은 날짜입니다.') from None


def positive_int(value, upper=None):
    if not re.fullmatch(r'[0-9]+', value) or len(value) > 9:
        raise ValueError('페이지는 양의 정수여야 합니다.')
    result = int(value)
    if result < 1 or (upper is not None and result > upper):
        raise ValueError('페이지 범위가 올바르지 않습니다.')
    return result


def comparison(params):
    value = params.get('comparison_type', 'agency')
    if value not in ('agency', 'market'):
        raise ValueError('지원하지 않는 비교 유형입니다.')
    return value


@app.get('/')
def root():
    return {'message': '실제 구매 자료 조회 API. 등록된 비교 정책이 있을 때 분석합니다.', 'synthetic': False, 'docs': '/docs'}


@app.get('/api/options')
def options(request: Request):
    try:
        validate_params(request, set())
        records, _ = load_data()
        agencies = {r['agency_id']: r['agency_name'] for r in records}
        items = {r['item_id']: r['item_name'] for r in records if r.get('item_id')}
        return {'agencies': [{'id': k, 'name': v} for k, v in sorted(agencies.items())],
                'items': [{'id': k, 'name': v} for k, v in sorted(items.items())]}
    except ValueError:
        return error(400, 'INVALID_REQUEST', '요청 조건을 확인해 주세요.')
    except (DataError, OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '데이터를 불러올 수 없습니다.')


@app.get('/api/purchases')
def purchases(request: Request):
    try:
        p = validate_params(request, {'q', 'agency_id', 'item_id', 'date_from', 'date_to', 'comparison_type', 'status', 'sort', 'page', 'page_size'})
        kind = comparison(p)
        query = p.get('q', '').strip()
        if len(query) > 200:
            raise ValueError('검색어는 200자 이하여야 합니다.')
        start = parse_date(p['date_from']) if 'date_from' in p else None
        end = parse_date(p['date_to']) if 'date_to' in p else None
        if start and end and start > end:
            raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
        status = p.get('status')
        if status is not None and status not in ('comparable', 'insufficient_data', 'conditions_unknown', 'unavailable'):
            raise ValueError('지원하지 않는 상태입니다.')
        order = p.get('sort', 'purchased_desc')
        if order not in ('purchased_desc', 'difference_pct_desc') or (order == 'difference_pct_desc' and not p.get('item_id')):
            raise ValueError('정렬 조건을 확인해 주세요.')
        page = positive_int(p.get('page', '1'))
        page_size = positive_int(p.get('page_size', '20'), 100)
        records, version = load_data()
        engine, market, version = comparison_context(records, version)
        filtered = []
        for r in records:
            if p.get('agency_id') and r['agency_id'] != p['agency_id']:
                continue
            if p.get('item_id') and r.get('item_id') != p['item_id']:
                continue
            if query and not any(query.casefold() in (r.get(k) or '').casefold() for k in ('item_name', 'model', 'agency_name')):
                continue
            day = r.get('purchased_at')
            if (start or end) and (not day or (start and day < start) or (end and day > end)):
                continue
            filtered.append(r)
        filtered.sort(key=lambda r: r['record_id'])
        results = {}
        def result(r):
            key = r['record_id']
            if key not in results:
                results[key] = analyze(r, records, market, version, kind, engine)
            return results[key]

        if status:
            if engine is None:
                if status != 'unavailable':
                    filtered = []
            else:
                # B always returns unavailable when a target is not active.
                filtered = [r for r in filtered if (status == 'unavailable' if r.get('status') != 'active' else result(r)['status'] == status)]
        if order == 'purchased_desc':
            filtered.sort(key=lambda r: r.get('purchased_at') or '', reverse=True)
        elif engine is not None:
            # Non-active targets always have a null difference; keep their ID order.
            def rank(r):
                if r.get('status') != 'active':
                    return (1, Decimal(0))
                value = result(r)['difference_pct']
                return (1, Decimal(0)) if value is None else (0, -Decimal(value))
            filtered.sort(key=rank)
        total = len(filtered)
        selected = filtered[(page - 1) * page_size:page * page_size]
        return {'contract_version': '1.0', 'dataset_version': version, 'synthetic': False,
                'items': [result(r) for r in selected], 'total': total,
                'page': page, 'page_size': page_size}
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (DataError, OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '데이터를 불러올 수 없습니다.')


@app.get('/api/purchases/{record_id:path}')
def purchase(record_id: str, request: Request):
    try:
        p = validate_params(request, {'comparison_type'})
        kind = comparison(p)
        records, version = load_data()
        engine, market, version = comparison_context(records, version)
        for record in records:
            if record['record_id'] == record_id:
                return analyze(record, records, market, version, kind, engine)
        return error(404, 'NOT_FOUND', '구매 기록을 찾을 수 없습니다.')
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (DataError, OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '데이터를 불러올 수 없습니다.')


@app.get('/api/explanations/{record_id:path}')
def explanation(record_id: str, request: Request):
    try:
        p = validate_params(request, {'comparison_type'})
        kind = comparison(p)
        records, version = load_data()
        engine, market, version = comparison_context(records, version)
        record = next((r for r in records if r['record_id'] == record_id), None)
        if record is None:
            return error(404, 'NOT_FOUND', '구매 기록을 찾을 수 없습니다.')
        analysis = analyze(record, records, market, version, kind, engine)
        try:
            gemini.load_env()
            generate = gemini.make_generate()
        except (gemini.GeminiError, OSError, UnicodeError):
            generate = None
        return explain_analysis(analysis, generate)
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (DataError, OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '데이터를 불러올 수 없습니다.')


@app.get('/api/preliminary')
def preliminary_batch(request: Request):
    try:
        params = request.query_params
        if set(params) - {'record_id', 'comparison_type'} or len(params.getlist('comparison_type')) > 1:
            raise ValueError('요청 조건을 확인해 주세요.')
        ids = params.getlist('record_id')
        if not ids or len(ids) > 100 or len(set(ids)) != len(ids) or any(not value or len(value) > 200 for value in ids):
            raise ValueError('구매 ID는 1~100개여야 합니다.')
        kind = comparison(params)
        items = []
        for record_id in ids:
            item = preliminary(record_id, kind)
            if item is not None:
                items.append({k: v for k, v in item.items() if k not in ('comparison_records', 'limitations')})
        return {'items': items}
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '참고 자료를 불러올 수 없습니다.')


@app.get('/api/preliminary/{record_id:path}')
def preliminary_comparison(record_id: str, request: Request):
    try:
        p = validate_params(request, {'comparison_type'})
        result = preliminary(record_id, comparison(p))
        return result if result is not None else error(404, 'NOT_FOUND', '구매 기록을 찾을 수 없습니다.')
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '참고 자료를 불러올 수 없습니다.')
