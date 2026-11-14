"""Read-only purchase search. Comparison is unavailable until B's engine is connected."""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = ROOT / 'data' / 'demo' / 'purchases.json'
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
            'reasons': ['비교 함수와 실제 비교 정책이 연결되지 않아 분석하지 않았습니다.'],
            'target': record, 'reference_unit_price': None, 'difference': None,
            'difference_pct': None, 'comparison_records': [], 'excluded_records': [],
            'comparison_count': 0, 'agency_count': 0 if comparison_type == 'agency' else None,
            'comparison_period': PERIOD, 'method_version': 'unit-price-v1',
            'policy_id': 'not-configured', 'evidence_ids': [record['record_id']],
            'limitations': ['비교 결과가 아닙니다. 표시된 기간은 원본 자료의 수집 범위입니다.',
                            '계약 상태와 세금·배송·설치 조건은 원본에서 확인되지 않았을 수 있습니다.']}


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
    return {'message': '실제 시연 구매 자료 조회 API. 가격 비교 기능은 아직 연결되지 않았습니다.', 'synthetic': False, 'docs': '/docs'}


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
            if status and status != 'unavailable':
                continue
            filtered.append(r)
        filtered.sort(key=lambda r: r['record_id'])
        if order == 'purchased_desc':
            filtered.sort(key=lambda r: r.get('purchased_at') or '', reverse=True)
        total = len(filtered)
        selected = filtered[(page - 1) * page_size:page * page_size]
        return {'contract_version': '1.0', 'dataset_version': version, 'synthetic': False,
                'items': [unavailable(r, version, kind) for r in selected], 'total': total,
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
        for record in records:
            if record['record_id'] == record_id:
                return unavailable(record, version, kind)
        return error(404, 'NOT_FOUND', '구매 기록을 찾을 수 없습니다.')
    except ValueError as exc:
        return error(400, 'INVALID_REQUEST', str(exc))
    except (DataError, OSError, KeyError, TypeError):
        return error(500, 'INTERNAL_ERROR', '데이터를 불러올 수 없습니다.')
