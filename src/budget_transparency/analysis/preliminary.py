"""Clearly labelled provisional price arithmetic; not the strict v1 comparison."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/shared/provinces-20251114-20261113'
FIELDS = ('item_id', 'model', 'specification', 'unit', 'currency')
LIMITATIONS = [
    '참고용 단순 가격 차이입니다. 이상 거래, 부패, 예산 낭비 또는 절감액을 뜻하지 않습니다.',
    '계약 상태와 세금·배송·설치비 등 포함 조건이 확인되지 않아 동등한 조건의 가격 비교가 아닐 수 있습니다.',
    '구매 시점과 수량, 거래 조건이 서로 다를 수 있으며 가격 차이의 원인은 확인되지 않았습니다.',
]


def price(value):
    try:
        number = Decimal(value) if isinstance(value, str) else Decimal(0)
        return number if number.is_finite() and number > 0 else None
    except InvalidOperation:
        return None


def key(row):
    values = tuple(row.get(field) for field in FIELDS)
    return values if all(isinstance(v, str) and v.strip() for v in values) else None


@lru_cache(maxsize=1)
def _dataset(signature):
    purchases, markets, links = [json.loads((DATA / name).read_text()) for name in ('purchases.json', 'market-prices.json', 'purchase-list.json')]
    rows = {r['record_id']: r for r in purchases}
    market_by_id = {r['market_price_id']: r for r in markets}
    links_by_id = {r['record_id']: r for r in links}
    groups = defaultdict(list)
    for row in purchases:
        group = key(row)
        if group and row.get('status') in ('active', 'unknown') and price(row.get('unit_price')):
            groups[group].append(row)
    return rows, market_by_id, links_by_id, groups


def _load():
    files = [DATA / n for n in ('purchases.json', 'market-prices.json', 'purchase-list.json')]
    return _dataset(tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in files))


def preliminary(record_id, kind):
    rows, market_by_id, links, groups = _load()
    target = rows.get(record_id)
    if target is None:
        return None
    group = key(target)
    reasons = []
    candidates = []
    if target.get('status') not in ('active', 'unknown') or not price(target.get('unit_price')) or not group:
        reasons.append('대상 기록의 상태, 단가 또는 제품 식별 정보가 부족합니다.')
    elif kind == 'agency':
        candidates = [r for r in groups[group] if r['record_id'] != record_id and r.get('agency_id') != target.get('agency_id')]
    elif kind == 'market':
        link = links.get(record_id, {})
        if link.get('search_result') == 'verified':
            seen_sellers = set()
            matched = [market_by_id[mid] for mid in (link.get('market_price_ids') or []) if mid in market_by_id]
            for row in sorted(matched, key=lambda r: (r.get('checked_at') or '', r['market_price_id']), reverse=True):
                seller = row.get('seller_name')
                if key(row) == group and price(row.get('price')) and seller and seller not in seen_sellers:
                    seen_sellers.add(seller)
                    candidates.append(row)
    else:
        raise ValueError('invalid comparison type')
    if not candidates and not reasons:
        reasons.append('같은 제품과 단위의 참고 가격 자료가 없습니다.')
    amounts = sorted(price(r['unit_price' if kind == 'agency' else 'price']) for r in candidates)
    reference = difference = pct = None
    if amounts:
        with localcontext() as ctx:
            ctx.prec = 64
            n = len(amounts)
            median = amounts[n // 2] if n % 2 else (amounts[n // 2 - 1] + amounts[n // 2]) / 2
            diff = price(target['unit_price']) - median
            reference, difference = format(median, 'f'), format(diff, 'f')
            pct = format((diff / median * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')
    limitations = LIMITATIONS.copy()
    if kind == 'market':
        limitations.append('시중가는 조사일의 판매가이며 기관 구매 당시의 시중가가 아닐 수 있습니다. 판매처 표본이 시장 전체를 대표하지 않습니다.')
    return {'record_id': record_id, 'comparison_type': kind, 'label': '조건 미확인 참고 비교',
            'reference_unit_price': reference, 'difference': difference, 'difference_pct': pct,
            'comparison_count': len(candidates), 'comparison_records': candidates,
            'reasons': reasons, 'limitations': limitations}
