"""Contract v1 unit-price comparison, with no file, server or model access.

E supplies a validated policy and dataset version at startup. Prefer one
ComparisonEngine per dataset; configure_analysis provides the four-argument
module function for a server using a single dataset. Input rows are normalized
contract-v1 dictionaries. They and the returned evidence are never mutated.
"""
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
import re


PRODUCT_FIELDS = ("item_id", "model", "specification", "unit", "currency")
COST_FIELDS = ("tax_included", "delivery_included", "installation_included")
KOREA = timezone(timedelta(hours=9))
DECIMAL_STRING = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?\Z")
DATE_STRING = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class AnalysisConfigurationError(RuntimeError):
    """A registered policy and dataset version must be provided by E."""


class PurchaseNotFoundError(LookupError):
    """The requested record does not exist; the server can map this to 404."""


def _day(value):
    if not isinstance(value, str) or not DATE_STRING.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _positive(value):
    if not isinstance(value, str) or not DECIMAL_STRING.fullmatch(value):
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    return result if result.is_finite() and result > 0 else None


def _checked_at(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            return None
        return result.astimezone(KOREA)
    except (ValueError, OverflowError):
        return None


def _in_period(day, period):
    return day is not None and period["from"] <= day.isoformat() <= period["to"]


def _condition_reason(row, target=None):
    for field in PRODUCT_FIELDS:
        if not isinstance(row.get(field), str) or not row[field].strip():
            return f"제품 식별·단위·통화 불명: {field}"
        if target is not None and row[field] != target[field]:
            return f"다른 물품·규격·단위·통화: {field}"
    if row["currency"] != "KRW":
        return "지원하지 않는 통화"
    for field in COST_FIELDS:
        if type(row.get(field)) is not bool:
            return f"포함 비용 조건 불명: {field}"
        if target is not None and row[field] != target[field]:
            return f"포함 비용 조건 불일치: {field}"
    return None


def _check_rows(rows, id_key, synthetic):
    if not isinstance(rows, list):
        raise ValueError("Normalized records must be a list")
    ids = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(id_key), str) or not row[id_key]:
            raise ValueError(f"Missing {id_key}")
        if type(row.get("synthetic")) is not bool or row["synthetic"] != synthetic:
            raise ValueError("Mixed real and synthetic records")
        ids.append(row[id_key])
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate {id_key}; normalize data before comparison")


def _prices(target_price, prices):
    # Enough precision for exact addition/subtraction even for long decimal
    # strings. This context does not change the caller's Decimal context.
    values = [target_price, *prices]
    width = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + 1
    with localcontext() as context:
        context.prec = max(28, 2 * width + 32)
        ordered = sorted(prices)
        middle = len(ordered) // 2
        reference = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        difference = target_price - reference
        pct = (difference / reference * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Do not emit -0.00 for a small negative difference.
        if pct == 0:
            pct = abs(pct)
        return format(reference, "f"), format(difference, "f"), format(pct, ".2f")


class ComparisonEngine:
    """An explicitly configured, dataset-specific analysis module.

    Constructor arguments are already-loaded objects, not file paths. A missing
    policy raises AnalysisConfigurationError: v1 has no valid representation of
    absent policy_id/comparison_period. See analysis/README.md for this boundary.
    """

    def __init__(self, policy, dataset_version):
        if not isinstance(dataset_version, str) or not dataset_version.strip():
            raise AnalysisConfigurationError("dataset_version is required")
        if not isinstance(policy, dict):
            raise AnalysisConfigurationError("A registered comparison policy is required")
        required = {"policy_id", "agency_period", "market_period", "min_peer_records",
                    "min_peer_agencies", "quantity_rule", "agency_reference",
                    "market_reference", "conditions_rule"}
        if set(policy) != required or not isinstance(policy["policy_id"], str) or not policy["policy_id"].strip():
            raise AnalysisConfigurationError("Invalid policy fields")
        for key in ("agency_period", "market_period"):
            period = policy[key]
            if (not isinstance(period, dict) or set(period) != {"from", "to"}
                    or _day(period["from"]) is None or _day(period["to"]) is None
                    or period["from"] > period["to"]):
                raise AnalysisConfigurationError("Invalid policy period")
        for key in ("min_peer_records", "min_peer_agencies"):
            if type(policy[key]) is not int or policy[key] < 1:
                raise AnalysisConfigurationError("Invalid policy minimum")
        expected = {"quantity_rule": "equal", "agency_reference": "record_median",
                    "market_reference": "median", "conditions_rule": "known_equal"}
        if any(policy[key] != value for key, value in expected.items()):
            raise AnalysisConfigurationError("Unsupported comparison policy rule")
        self._policy = deepcopy(policy)
        self._dataset_version = dataset_version

    def compare_purchase(self, record_id, purchases, market_prices, comparison_type):
        """Return an analysis-v1 dict, or raise for an invalid request/dataset."""
        if comparison_type not in ("agency", "market"):
            raise ValueError("comparison_type must be agency or market")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be a nonempty string")
        if not isinstance(purchases, list) or any(not isinstance(r, dict) for r in purchases):
            raise ValueError("purchases must be normalized dictionaries")
        matches = [r for r in purchases if r.get("record_id") == record_id]
        if not matches:
            raise PurchaseNotFoundError("Purchase record not found")
        target = matches[0]
        _check_rows(purchases, "record_id", target.get("synthetic"))
        _check_rows(market_prices, "market_price_id", target["synthetic"])
        policy = self._policy
        period = policy["agency_period" if comparison_type == "agency" else "market_period"]
        result = {
            "contract_version": "1.0", "dataset_version": self._dataset_version,
            "record_id": record_id, "comparison_type": comparison_type,
            "synthetic": target["synthetic"], "status": "unavailable", "reasons": [],
            "target": deepcopy(target), "reference_unit_price": None,
            "difference": None, "difference_pct": None, "comparison_records": [],
            "excluded_records": [], "comparison_count": 0,
            "agency_count": 0 if comparison_type == "agency" else None,
            "comparison_period": deepcopy(period), "method_version": "unit-price-v1",
            "policy_id": policy["policy_id"], "evidence_ids": [record_id],
            "limitations": [],
        }
        if target["synthetic"]:
            result["limitations"].append("합성 데이터이며 실제 공공기관 분석이 아닙니다.")
        if target.get("status") != "active":
            result["reasons"].append("대상 구매 상태가 유효한 active로 확인되지 않았습니다.")
        if _positive(target.get("unit_price")) is None or _positive(target.get("quantity")) is None:
            result["reasons"].append("대상 단가·수량이 누락되었거나 양수가 아닙니다.")
        if not _in_period(_day(target.get("purchased_at")), policy["agency_period"]):
            result["reasons"].append("대상 구매일이 유효하지 않거나 구매 정책 기간 밖입니다.")
        if result["reasons"]:
            return result
        unknown = _condition_reason(target)
        if unknown:
            result.update(status="conditions_unknown", reasons=[unknown])
            return result

        excluded = result["excluded_records"]
        peers = []
        if comparison_type == "agency":
            seen_sources = {}
            for row in sorted(purchases, key=lambda r: r["record_id"]):
                if row["record_id"] == record_id:
                    continue
                reason = self._agency_reason(row, target)
                # Source row identity, not parent contract number, identifies a
                # duplicated normalized transaction. A selects latest revisions.
                source = (row.get("source_id"), row.get("source_record_id"), row.get("agency_id"))
                if not reason and all(source):
                    previous = seen_sources.get(source)
                    if previous is not None:
                        left = {k: v for k, v in previous.items() if k != "record_id"}
                        right = {k: v for k, v in row.items() if k != "record_id"}
                        if left != right:
                            raise ValueError("Conflicting copies of the same source row")
                        reason = "동일 출처 원본 행 중복"
                    else:
                        seen_sources[source] = row
                if reason:
                    excluded.append({"id": row["record_id"], "reason": reason})
                else:
                    peers.append(row)
        else:
            peers = self._market_peers(market_prices, target, period, excluded)

        key = "record_id" if comparison_type == "agency" else "market_price_id"
        peers.sort(key=lambda r: r[key])
        if record_id in {r[key] for r in peers}:
            raise ValueError("Purchase and market evidence IDs must be distinct")
        excluded.sort(key=lambda r: r["id"])
        result["comparison_records"] = deepcopy(peers)
        result["comparison_count"] = len(peers)
        result["evidence_ids"].extend(r[key] for r in peers)
        if comparison_type == "agency":
            result["agency_count"] = len({r["agency_id"] for r in peers})
            sufficient = (len(peers) >= policy["min_peer_records"]
                          and result["agency_count"] >= policy["min_peer_agencies"])
        else:
            sufficient = bool(peers)
        if not sufficient:
            result.update(status="insufficient_data", reasons=["적격 비교 건수 또는 기관 수가 부족합니다."
                          if comparison_type == "agency" else "확인된 적격 시중가가 없습니다."])
            return result

        price_key = "unit_price" if comparison_type == "agency" else "price"
        reference, difference, pct = _prices(_positive(target["unit_price"]), [_positive(r[price_key]) for r in peers])
        result.update(status="comparable", reference_unit_price=reference, difference=difference, difference_pct=pct)
        if comparison_type == "market" and len(peers) < 3:
            result["limitations"].append("시중가 판매처 표본이 적어 시장 전체를 대표하지 않습니다.")
        return result

    def _agency_reason(self, row, target):
        if row.get("agency_id") == target["agency_id"]:
            return "대상 기관의 구매"
        if row.get("status") != "active":
            return "취소·이전 변경본 또는 유효 상태 불명"
        if _positive(row.get("unit_price")) is None or _positive(row.get("quantity")) is None:
            return "단가·수량이 누락되었거나 양수가 아님"
        if not _in_period(_day(row.get("purchased_at")), self._policy["agency_period"]):
            return "유효 구매일 없음 또는 정책 기간 밖"
        reason = _condition_reason(row, target)
        if reason:
            return reason
        if _positive(row["quantity"]) != _positive(target["quantity"]):
            return "구매 수량 불일치"
        return None

    def _market_peers(self, rows, target, period, excluded):
        sellers = {}
        for row in rows:
            stamp = _checked_at(row.get("checked_at"))
            reason = None
            if not _in_period(stamp.date() if stamp else None, period):
                reason = "유효 확인일 없음 또는 정책 기간 밖"
            elif row.get("item_id") != target["item_id"]:
                reason = "다른 물품"
            elif not isinstance(row.get("seller_name"), str) or not row["seller_name"].strip():
                reason = "판매처 불명"
            if reason:
                excluded.append({"id": row["market_price_id"], "reason": reason})
                continue
            sellers.setdefault((row["seller_name"], row["item_id"]), []).append((stamp, row))
        peers = []
        for records in sellers.values():
            # Select latest first: do not substitute an older price when the
            # latest observation has unknown/incompatible conditions.
            records.sort(key=lambda pair: pair[1]["market_price_id"])
            records.sort(key=lambda pair: pair[0], reverse=True)
            latest = records[0][1]
            for _, old in records[1:]:
                excluded.append({"id": old["market_price_id"], "reason": "동일 판매처·제품의 이전 확인 또는 동률 ID 후순위"})
            reason = _condition_reason(latest, target)
            if reason is None and _positive(latest.get("price")) is None:
                reason = "시중가가 누락되었거나 양수가 아님"
            if reason:
                excluded.append({"id": latest["market_price_id"], "reason": reason})
            else:
                peers.append(latest)
        return peers


_default_engine = None


def configure_analysis(policy, dataset_version):
    """Configure the single-dataset module function at startup; return the engine.

    For multiple datasets or concurrent versions use independent engines instead
    of reconfiguring this module per HTTP request.
    """
    engine = ComparisonEngine(policy, dataset_version)
    global _default_engine
    _default_engine = engine
    return engine


def compare_purchase(record_id, purchases, market_prices, comparison_type):
    """Compare already-loaded contract-v1 rows using E's configured policy."""
    if _default_engine is None:
        raise AnalysisConfigurationError("Call configure_analysis with a registered policy and dataset version first")
    return _default_engine.compare_purchase(record_id, purchases, market_prices, comparison_type)
