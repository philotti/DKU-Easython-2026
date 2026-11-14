"""분석 결과 설명. 화면에 나가는 문장은 모두 코드가 만든 고정 문장이다.

모델은 문장을 쓰지 않는다. 코드가 제공한 확인 사항 목록에서 관련 있는 항목의 ID만 고른다.
목록에 없는 ID나 자유 문장이 오면 응답 전체를 버리고 기본 안내를 반환한다.
가격·차이율·높낮이는 화면이 분석 응답의 값으로 직접 표시한다.

generate는 (system, user) 문자열을 받아 모델의 응답 문자열을 돌려주는 함수다.
이 모듈은 SDK와 키를 다루지 않는다.
"""
import json
import re
from decimal import Decimal

from . import prompts

AI_CAUTIONS_MAX = 3
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

# 모델이 고를 수 있는 확인 사항. 모두 "확인하세요"로 끝나며 사실·원인을 단정하지 않는다.
_CHECKS = {
    "tax": "세금 포함 여부를 확인하세요.",
    "delivery": "배송비 포함 여부를 확인하세요.",
    "installation": "설치비 포함 여부를 확인하세요.",
    "specification": "제품 규격과 모델이 같은지 확인하세요.",
    "quantity": "수량과 단위가 같은지 확인하세요.",
    "timing": "구매 시점이 같은지 확인하세요.",
    "contract": "계약 조건과 계약 방식을 확인하세요.",
    "excluded": "비교에서 제외된 기록과 제외 사유를 확인하세요.",
    "market": "시중가 자료의 판매 조건과 확인 시점을 확인하세요.",
    "source": "원본 기록에서 내용을 확인하세요.",
}


def available_checks(analysis):
    """이 분석 결과에 대해 모델이 고를 수 있는 확인 사항 {id: 문장}."""
    checks = dict(_CHECKS)
    if not analysis["excluded_records"]:
        del checks["excluded"]
    if analysis["comparison_type"] != "market":
        del checks["market"]
    return checks


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


def fixed_summary(analysis):
    """상태만으로 정하는 고정 요약. 숫자와 원인을 쓰지 않는다."""
    if analysis.get('_preliminary'):
        if analysis.get('difference') is None:
            return '조건 미확인 참고 비교에 필요한 자료가 부족합니다. 구매 내역과 확인 사항을 살펴보세요.'
        if Decimal(analysis['difference']) == 0:
            return '참고 기준 단가와 같습니다. 계약 상태와 비용 조건은 확인이 필요합니다.'
        return '참고 기준 단가와 차이가 있습니다. 계약 상태와 비용 조건은 확인이 필요합니다.'
    if analysis["status"] == "comparable":
        if Decimal(analysis["difference"]) == 0:
            return _SAME_PRICE_SUMMARY
        return _COMPARABLE_SUMMARY[analysis["comparison_type"]]
    return _FALLBACK_SUMMARY.get(analysis["status"], _FALLBACK_SUMMARY["unavailable"])


def fallback_explanation(analysis):
    """AI 없이 만드는 기본 안내."""
    return _response(analysis, fixed_summary(analysis), list(analysis["evidence_ids"]), _cautions(analysis), "fallback")


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


def _id_list(value, allowed, maximum=None):
    """중복 없는 문자열 목록이고 모두 allowed 안에 있어야 한다."""
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise ValueError("expected non-empty list of strings")
    if len(value) != len(set(value)) or not set(value) <= set(allowed):
        raise ValueError("duplicate or unknown id")
    if maximum is not None and len(value) > maximum:
        raise ValueError("too many ids")
    return value


def validate_explanation(raw, analysis):
    """모델 응답 문자열을 검증해 계약 형식으로 만든다. 문제가 있으면 ValueError.

    모델 응답은 {"evidence_ids": [...], "caution_ids": [...]}만 허용한다. 문장은 받지 않는다.
    """
    value = _load_json_object(raw)
    if set(value) != {"evidence_ids", "caution_ids"}:
        raise ValueError("unexpected keys")
    evidence_ids = _id_list(value["evidence_ids"], analysis["evidence_ids"])
    checks = available_checks(analysis)
    caution_ids = _id_list(value["caution_ids"], checks, AI_CAUTIONS_MAX)
    chosen = [checks[i] for i in caution_ids]
    return _response(analysis, fixed_summary(analysis), evidence_ids, _cautions(analysis, chosen), "ai")


def explain_analysis(analysis, generate=None):
    """analysis.schema.json 형식의 분석 결과를 explanation.schema.json 형식으로 설명한다.

    summary와 cautions의 문장은 두 mode 모두 코드가 만든 고정 문장이다. mode=ai이면
    모델이 목록에서 고른 확인 사항이 cautions에 더해진다. generate가 없거나, 호출이
    실패하거나, 응답이 검증을 통과하지 못하면 mode=fallback.
    """
    fallback = fallback_explanation(analysis)
    if generate is None:
        return fallback
    try:
        raw = generate(prompts.EXPLAIN_SYSTEM, prompts.build_explain_prompt(analysis, available_checks(analysis)))
        return validate_explanation(raw, analysis)
    except Exception:  # 시간 초과·한도 초과·형식 오류 모두 기본 안내로 대체
        return fallback
