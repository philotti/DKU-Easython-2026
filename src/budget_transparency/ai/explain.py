"""분석 결과 설명. 모델 응답은 검증을 통과할 때만 쓰고, 아니면 기본 안내를 반환한다.

generate는 (system, user) 문자열을 받아 모델의 응답 문자열을 돌려주는 함수다.
실제 모델 호출 함수는 E와 함께 정한다. 이 모듈은 SDK와 키를 다루지 않는다.
"""
import json
import re
from decimal import Decimal, InvalidOperation

from . import prompts

SUMMARY_MAX = 300
SYNTHETIC_CAUTION = "합성 데이터이며 실제 공공기관 분석이 아닙니다."

_FALLBACK_SUMMARY = {
    "insufficient_data": "비교 자료가 부족해 가격 차이를 계산하지 않았습니다.",
    "conditions_unknown": "가격 조건이 확인되지 않아 가격 차이를 계산하지 않았습니다.",
    "unavailable": "이 구매 기록은 분석할 수 없어 가격 차이를 계산하지 않았습니다.",
}
_COMPARABLE_SUMMARY = {
    "agency": "다른 기관의 비교 가능한 구매 기록과 단가 차이가 있습니다. 포함 비용과 계약 조건을 함께 확인하세요.",
    "market": "확인된 시중가 자료와 단가 차이가 있습니다. 판매 조건과 확인 시점을 함께 확인하세요.",
}
_SAME_PRICE_SUMMARY = "비교 기준 단가와 같습니다. 포함 비용과 계약 조건을 함께 확인하세요."

# 단정·절감 표현과 URL은 부정문이어도 통과시키지 않는다(보수적으로 기본 안내로 대체).
_BANNED = ("비리", "부패", "횡령", "불법", "낭비", "절감", "http://", "https://", "www.")
_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_MAGNITUDE = "만억천백조"


def _cautions(analysis, extra=()):
    result = []
    for text in [*analysis["limitations"], *extra]:
        if text not in result:
            result.append(text)
    if analysis["synthetic"] and not any("합성" in text for text in result):
        result.insert(0, SYNTHETIC_CAUTION)
    return result


def _response(analysis, summary, evidence_ids, cautions, mode):
    return {
        "contract_version": "1.0",
        "dataset_version": analysis["dataset_version"],
        "record_id": analysis["record_id"],
        "comparison_type": analysis["comparison_type"],
        "summary": summary,
        "evidence_ids": evidence_ids,
        "cautions": cautions,
        "mode": mode,
    }


def fallback_explanation(analysis):
    """AI 없이 상태만으로 만드는 기본 안내. 숫자와 원인을 쓰지 않는다."""
    if analysis["status"] == "comparable":
        if Decimal(analysis["difference"]) == 0:
            summary = _SAME_PRICE_SUMMARY
        else:
            summary = _COMPARABLE_SUMMARY[analysis["comparison_type"]]
    else:
        summary = _FALLBACK_SUMMARY.get(analysis["status"], _FALLBACK_SUMMARY["unavailable"])
    return _response(analysis, summary, list(analysis["evidence_ids"]), _cautions(analysis), "fallback")


def _allowed_numbers(analysis):
    target = analysis["target"]
    values = [
        analysis["reference_unit_price"],
        analysis["difference"],
        analysis["difference_pct"],
        analysis["comparison_count"],
        analysis["agency_count"],
        target["unit_price"],
        target["quantity"],
    ]
    allowed = set()
    for value in values:
        if value is None:
            continue
        number = Decimal(str(value))
        allowed.update((number, abs(number)))
    return allowed


def _known_strings(analysis):
    target = analysis["target"]
    period = analysis["comparison_period"] or {}
    known = [
        target["purchased_at"],
        period.get("from"),
        period.get("to"),
        target["model"],
        target["item_name"],
        target["agency_name"],
        target["specification"],
        *analysis["evidence_ids"],
    ]
    return sorted((s for s in known if s), key=len, reverse=True)


def _check_text(text, analysis):
    for word in _BANNED:
        if word in text:
            raise ValueError("banned expression")
    for known in _known_strings(analysis):
        text = text.replace(known, " ")
    allowed = _allowed_numbers(analysis)
    for match in _NUMBER.finditer(text):
        if text[match.end():match.end() + 1] in _MAGNITUDE and match.end() < len(text):
            raise ValueError("unverifiable number")
        try:
            number = Decimal(match.group().replace(",", ""))
        except InvalidOperation:
            raise ValueError("unverifiable number") from None
        if number not in allowed:
            raise ValueError("number not in analysis")


def _load_json_object(raw):
    if not isinstance(raw, str):
        raise ValueError("response is not text")
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("response is not an object")
    return value


def _string_list(value):
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ValueError("expected list of non-empty strings")
    return [v.strip() for v in value]


def validate_explanation(raw, analysis):
    """모델 응답 문자열을 검증해 계약 형식으로 만든다. 문제가 있으면 ValueError."""
    value = _load_json_object(raw)
    if set(value) != {"summary", "evidence_ids", "cautions"}:
        raise ValueError("unexpected keys")
    summary = value["summary"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > SUMMARY_MAX:
        raise ValueError("invalid summary")
    summary = summary.strip()
    evidence_ids = _string_list(value["evidence_ids"])
    if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("invalid evidence ids")
    if not set(evidence_ids) <= set(analysis["evidence_ids"]):
        raise ValueError("unknown evidence id")
    cautions = _string_list(value["cautions"])
    for text in [summary, *cautions]:
        _check_text(text, analysis)
    return _response(analysis, summary, evidence_ids, _cautions(analysis, cautions), "ai")


def explain_analysis(analysis, generate=None):
    """analysis.schema.json 형식의 분석 결과를 explanation.schema.json 형식으로 설명한다.

    generate가 없거나, 호출이 실패하거나, 응답이 검증을 통과하지 못하면 mode=fallback.
    """
    fallback = fallback_explanation(analysis)
    if generate is None:
        return fallback
    try:
        raw = generate(prompts.EXPLAIN_SYSTEM, prompts.build_explain_prompt(analysis))
        return validate_explanation(raw, analysis)
    except Exception:  # 시간 초과·한도 초과·형식 오류 모두 기본 안내로 대체
        return fallback
