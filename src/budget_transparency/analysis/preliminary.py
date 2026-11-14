"""Clearly labelled provisional price arithmetic; not the strict v1 comparison."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from datetime import date
from calendar import monthrange
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/shared/provinces-20251114-20261113'
OLD_DATA = ROOT / 'data/shared/provinces-20241114-20251113'
CITY_FILE = ROOT / 'data/shared/cities-20251114-20261113/purchase-seoul-pusan-dajeon.jason'
DATASETS = ((DATA, ('purchases.json', 'market-prices.json', 'purchase-list.json', 'same-items.json')),
            (OLD_DATA, ('purchases-24-25.json', 'market-prices-24-25.json', 'purchase-list-24-25.json', 'same-items-24-25.json')))
PERIOD = {'from': '2024-11-14', 'to': '2026-11-13'}
FIELDS = ('item_id', 'model', 'specification', 'unit', 'currency')
LIMITATIONS = [
    '참고용 단순 가격 차이입니다. 이상 거래, 부패, 예산 낭비 또는 절감액을 뜻하지 않습니다.',
    '계약 상태와 세금·배송·설치비 등 포함 조건이 확인되지 않아 동등한 조건의 가격 비교가 아닐 수 있습니다.',
    '거래 조건과 구매 시점이 다를 수 있으며 가격 차이의 원인은 확인되지 않았습니다.',
]


class PreliminaryDataError(Exception):
    """The shared candidate mapping does not match its purchase records."""


def price(value):
    try:
        number = Decimal(value) if isinstance(value, str) else Decimal(0)
        return number if number.is_finite() and number > 0 else None
    except InvalidOperation:
        return None


def key(row):
    values = tuple(row.get(field) for field in FIELDS)
    return values if all(isinstance(v, str) and v.strip() for v in values) else None


def agency_scope(row):
    if row.get('agency_id') in ('6460000', '6130769') and row.get('agency_name') == '전남광주통합특별시 무안청사':
        return 'scope:jeonnam-gwangju-muan'
    return row.get('agency_id')


def day(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def signature():
    files = [folder / name for folder, names in DATASETS for name in names] + [CITY_FILE]
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in files)


@lru_cache(maxsize=1)
def _dataset(signature):
    datasets = [[json.loads((folder / name).read_text()) for name in names] for folder, names in DATASETS]
    city_rows = json.loads(CITY_FILE.read_text())
    purchases = [r for purchase_rows, _, _, _ in datasets for r in purchase_rows] + city_rows
    markets = [r for _, market_rows, _, _ in datasets for r in market_rows]
    links = [r for _, _, link_rows, _ in datasets for r in link_rows]
    rows = {r['record_id']: r for r in purchases}
    if len(rows) != len(purchases):
        raise PreliminaryDataError('duplicate purchase record')
    market_by_id = {}
    for row in markets:
        rid = row['market_price_id']
        if rid in market_by_id and market_by_id[rid] != row:
            raise PreliminaryDataError('conflicting market record')
        market_by_id[rid] = row
    links_by_id = {r['record_id']: r for r in links}
    if len(links_by_id) != len(links):
        raise PreliminaryDataError('duplicate purchase link')
    groups = defaultdict(list)
    for row in purchases:
        group = key(row)
        if group and row.get('status') in ('active', 'unknown') and price(row.get('unit_price')):
            groups[group].append(row)
    # The shared grouping is a candidate index, never proof of matching costs
    # or contract status. Check every reference against the source files.
    shared = {}
    seen_groups = {}
    for _, _, _, same_items in datasets:
      dataset_groups = set()
      for group in same_items:
        group_id = group['group_id']
        if group_id in dataset_groups:
            raise PreliminaryDataError('duplicate group within dataset')
        dataset_groups.add(group_id)
        metadata = tuple(group.get(k, '').strip() for k in ('item_id', 'specification', 'unit', 'currency'))
        if group_id in seen_groups and seen_groups[group_id] != metadata:
            raise PreliminaryDataError('conflicting group metadata')
        seen_groups[group_id] = metadata
        members = []
        for province in group['provinces']:
            for member in province['purchases']:
                rid = member['record_id']
                row = rows.get(rid)
                if (rid in shared or row is None or links_by_id.get(rid, {}).get('group_id') != group_id
                    or any(member.get(k) != row.get(k) for k in ('purchased_at', 'quantity', 'unit_price'))
                    or any(not isinstance(row.get(k), str) or not isinstance(group.get(k), str)
                           or row[k].strip() != group[k].strip() for k in ('item_id', 'specification', 'unit', 'currency'))):
                    raise PreliminaryDataError('group and purchase records do not match')
                shared[rid] = (group_id, province['scope_agency_id'])
                members.append((row, province['scope_agency_id']))
        if len(members) != group['record_count'] or len({scope for _, scope in members}) != group['province_count']:
            raise PreliminaryDataError('group counts do not match')
        groups[('shared', group_id)].extend(members)
    # City rows have no same-items mapping. Join only when all product fields,
    # including the model, uniquely identify an existing shared group.
    group_keys = defaultdict(set)
    for group_key, members in groups.items():
        if len(group_key) == 2 and group_key[0] == 'shared':
            for row, _ in members:
                item_key = key(row)
                if item_key:
                    group_keys[item_key].add(group_key[1])
    for row in city_rows:
        matches = group_keys.get(key(row), set())
        if len(matches) == 1:
            group_id = next(iter(matches))
            scope = agency_scope(row)
            shared[row['record_id']] = (group_id, scope)
            groups[('shared', group_id)].append((row, scope))
    return rows, market_by_id, links_by_id, groups, shared


def _load():
    return _dataset(signature())


@lru_cache(maxsize=1)
def _ranking(signature):
    snapshot = _dataset(signature)
    rows, _, _, _, _ = snapshot
    results = []
    for row in rows.values():
        value = preliminary(row['record_id'], 'agency', snapshot)
        if value['difference_pct'] is None:
            continue
        results.append({'record_id': row['record_id'], 'agency_name': row['agency_name'],
                        'item_name': row['item_name'], 'purchased_at': row['purchased_at'],
                        'unit_price': row['unit_price'], 'reference_unit_price': value['reference_unit_price'],
                        'difference_pct': value['difference_pct'], 'comparison_count': value['comparison_count'],
                        'comparison_basis': value['comparison_basis'], 'agency_count': value['agency_count']})
    results.sort(key=lambda r: (-Decimal(r['difference_pct']), r['record_id']))
    return results, len(rows) - len(results)


def preliminary_ranking(page, page_size):
    results, excluded = _ranking(signature())
    start = (page - 1) * page_size
    return {'items': results[start:start + page_size], 'total': len(results), 'excluded_count': excluded,
            'page': page, 'page_size': page_size, 'period': PERIOD,
            'method': '동일 수량 우선, 부족하면 수량 0.5~2배·구매일 180일 이내의 다른 기관 3곳 및 5건 이상을 비교한 참고 차이율 순서.',
            'limitations': LIMITATIONS + ['기관 순위나 부패·낭비 점수가 아닙니다. 동일 기관의 여러 구매가 각각 표시될 수 있습니다.',
                '기관별 중앙값의 중앙값입니다. 표본·기간·수량 범위는 임시 기준이며 통계적 유의성이나 계약 조건 일치를 보장하지 않습니다.',
                '많은 구매를 정렬하면 우연히 큰 차이도 상위에 나타날 수 있습니다.']}


@lru_cache(maxsize=2)
def _available_ids(signature, kind):
    snapshot = _dataset(signature)
    rows, _, links, _, _ = snapshot
    if kind == 'agency':
        ranked, _ = _ranking(signature)
        return frozenset(r['record_id'] for r in ranked)
    if kind != 'market':
        raise ValueError('invalid comparison type')
    return frozenset(rid for rid in rows if links.get(rid, {}).get('search_result') == 'verified'
                     and preliminary(rid, kind, snapshot)['difference_pct'] is not None)


def preliminary_availability(kind):
    current = signature()
    return _available_ids(current, kind), len(_dataset(current)[0])


def preliminary_distribution(record_ids):
    ranked, _ = _ranking(signature())
    selected = [r for r in ranked if r['record_id'] in record_ids]
    higher = sum(Decimal(r['difference_pct']) > 0 for r in selected)
    lower = sum(Decimal(r['difference_pct']) < 0 for r in selected)
    equal = len(selected) - higher - lower
    return {'total': len(record_ids), 'compared': len(selected), 'excluded': len(record_ids) - len(selected),
            'higher': higher, 'equal': equal, 'lower': lower,
            'period': PERIOD}


def preliminary_examples(record_ids, limit=3):
    """Largest positive reference differences, scoped to the selected records."""
    ranked, _ = _ranking(signature())
    rows, _, _, _, _ = _load()
    examples = []
    for result in ranked:
        if result['record_id'] not in record_ids or Decimal(result['difference_pct']) <= 0:
            continue
        row = rows[result['record_id']]
        examples.append({**result, 'source_id': row.get('source_id'),
                         'source_record_id': row.get('source_record_id'), 'unit': row.get('unit')})
        if len(examples) >= limit:
            break
    return examples


def monthly_purchase_distribution(record_ids, coverage_from=None):
    rows, _, _, _, _ = _load()
    period_start, period_end = date(2024, 11, 14), date(2026, 11, 13)
    counts = defaultdict(int)
    undated = 0
    for rid in record_ids:
        purchased = day(rows[rid].get('purchased_at'))
        if purchased is None or not period_start <= purchased <= period_end:
            undated += 1
            continue
        counts[purchased.strftime('%Y-%m')] += 1
    months = []
    year, month = 2024, 11
    while (year, month) <= (2026, 11):
        key_month = f'{year:04d}-{month:02d}'
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        coverage_start = max(period_start, coverage_from) if coverage_from else period_start
        missing = last_day < coverage_start
        partial = not missing and (first_day < coverage_start or last_day > period_end)
        months.append({'month': key_month, 'count': None if missing else counts[key_month], 'partial': partial})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {'months': months, 'dated_total': sum(counts.values()), 'excluded': undated,
            'coverage_from': (coverage_from or period_start).isoformat(),
            'period': {'from': period_start.isoformat(), 'to': period_end.isoformat()}}


def preliminary(record_id, kind, snapshot=None):
    rows, market_by_id, links, groups, shared = snapshot if snapshot is not None else _load()
    target = rows.get(record_id)
    if target is None:
        return None
    group = key(target)
    reasons = []
    candidates = []
    basis = None
    agency_count = None
    shared_group = shared.get(record_id)
    if target.get('status') not in ('active', 'unknown') or not price(target.get('unit_price')):
        reasons.append('대상 기록의 상태, 단가 또는 제품 식별 정보가 부족합니다.')
    elif kind == 'agency':
        quantity = price(target.get('quantity'))
        target_day = day(target.get('purchased_at'))
        if quantity is None or target_day is None:
            reasons.append('대상 구매 수량 또는 구매일이 없거나 유효하지 않습니다.')
        elif shared_group:
            group_id, scope = shared_group
            possible = [(r, candidate_scope) for r, candidate_scope in groups[('shared', group_id)] if candidate_scope != scope]
        elif group:
            target_scope = agency_scope(target)
            possible = [(r, agency_scope(r)) for r in groups[group] if r['record_id'] != record_id and agency_scope(r) != target_scope]
        else:
            reasons.append('대상 기록의 제품 식별 정보가 부족합니다.')
        if not reasons:
            valid = [(r, scope) for r, scope in possible if scope and r.get('status') in ('active', 'unknown')
                     and price(r.get('unit_price')) and price(r.get('quantity')) and day(r.get('purchased_at'))
                     and abs((day(r['purchased_at']) - target_day).days) <= 180]
            exact = [(r, scope) for r, scope in valid if price(r['quantity']) == quantity]
            similar = [(r, scope) for r, scope in valid if quantity / 2 <= price(r['quantity']) <= quantity * 2]
            selected = exact if len(exact) >= 5 and len({scope for _, scope in exact}) >= 3 else similar
            agency_count = len({scope for _, scope in selected})
            candidates = [r for r, _ in selected]
            basis = 'same_quantity' if selected is exact else 'similar_quantity'
            if len(selected) < 5 or agency_count < 3:
                reasons.append(f'180일 이내 유사 수량 비교가 {len(selected)}건·다른 기관 {agency_count}곳으로 최소 5건·3곳에 미달합니다.')
    elif kind == 'market':
        link = links.get(record_id, {})
        if group and link.get('search_result') == 'verified':
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
    if amounts and not reasons:
        with localcontext() as ctx:
            ctx.prec = 64
            if kind == 'agency':
                by_agency = defaultdict(list)
                for row, scope in selected:
                    by_agency[scope].append(price(row['unit_price']))
                baseline = median([median(values) for values in by_agency.values()])
            else:
                baseline = median(amounts)
            diff = price(target['unit_price']) - baseline
            reference, difference = format(baseline, 'f'), format(diff, 'f')
            pct = format((diff / baseline * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')
    limitations = LIMITATIONS.copy()
    if kind == 'agency':
        limitations.append('구매일 180일 이내, 다른 기관 3곳·구매 5건 이상을 사용합니다. 같은 수량을 우선하고 부족하면 수량 0.5~2배 범위를 사용합니다. 이 기준은 임시 기준이며 통계적 유의성을 보장하지 않습니다.')
        limitations.append('기관별 중앙값을 각각 한 번씩 반영합니다. 일부 모델명과 계약 조건은 미확인입니다.')
    if kind == 'market':
        limitations.append('시중가는 조사일의 판매가이며 기관 구매 당시의 시중가가 아닐 수 있습니다. 판매처 표본이 시장 전체를 대표하지 않습니다.')
    return {'record_id': record_id, 'comparison_type': kind, 'label': '조건 미확인 참고 비교',
            'reference_unit_price': reference, 'difference': difference, 'difference_pct': pct,
            'comparison_basis': basis, 'agency_count': agency_count,
            'comparison_count': len(candidates), 'comparison_records': candidates,
            'reasons': reasons, 'limitations': limitations}
