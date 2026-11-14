"""분석 결과 설명. 요약 문장은 항상 코드가 만든 고정 문장이다.

모델은 '함께 확인할 점'만 쓴다. 가격·숫자·높낮이는 모델이 쓰지 못하게 하고,
그런 내용이 하나라도 있으면 응답 전체를 버리고 기본 안내를 반환한다.
가격·차이율·높낮이는 화면이 분석 응답의 값으로 직접 표시한다.

generate는 (system, user) 문자열을 받아 모델의 응답 문자열을 돌려주는 함수다.
이 모듈은 SDK와 키를 다루지 않는다.
"""
import json
import re
from decimal import Decimal

from . import prompts

CAUTION_MAX = 150
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

# 모델 문장에 있으면 안 되는 것. 부정문이어도 통과시키지 않는다(보수적으로 기본 안내로 대체).
_BANNED = ("비리", "부패", "횡령", "불법", "낭비", "절감", "http://", "https://", "www.")
_KOREAN_MONEY = re.compile(r"[일이삼사오육칠팔구십백천만억조]+\s*원")
# 가격의 높낮이·크기 비교. 계산 결과와 맞더라도 모델이 쓰지 못한다.
_COMPARISON = re.compile(
    r"보다|높|낮|비싸|비쌉|비쌌|싸|쌉|쌌|저렴|초과|미만|이상|이하|웃돌|밑돌|상회|하회|절반"
    r"|같습니다|같다|동일합니다|동일하다|차이가 없|차이 없"
    r"|적(?:습|다|은|게|었|어)|많(?:습|다|은|이|았|아)"
    r"|크(?:다|게)|큽니다|큰 |작(?:습|다|은|게|았|아)"
    r"|넘(?:습|는|었|어|다)|못 미|더 |덜 "
)


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
    if analysis["status"] == "comparable":
        if Decimal(analysis["difference"]) == 0:
            return _SAME_PRICE_SUMMARY
        return _COMPARABLE_SUMMARY[analysis["comparison_type"]]
    return _FALLBACK_SUMMARY.get(analysis["status"], _FALLBACK_SUMMARY["unavailable"])


def fallback_explanation(analysis):
    """AI 없이 만드는 기본 안내."""
    return _response(analysis, fixed_summary(analysis), list(analysis["evidence_ids"]), _cautions(analysis), "fallback")


def _known_strings(analysis):
    """숫자가 들어 있을 수 있는 이름·ID. 숫자 검사 전에 문장에서 지운다."""
    target = analysis["target"]
    known = [
        target["model"],
        target["item_name"],
        target["agency_name"],
        target["specification"],
        *analysis["evidence_ids"],
    ]
    return sorted((s for s in known if s), key=len, reverse=True)


def _check_text(text, analysis):
    if len(text) > CAUTION_MAX:
        raise ValueError("caution too long")
    for word in _BANNED:
        if word in text:
            raise ValueError("banned expression")
    for known in _known_strings(analysis):
        text = text.replace(known, " ")
    if re.search(r"\d", text) or _KOREAN_MONEY.search(text):
        raise ValueError("numbers are not allowed in AI text")
    if _COMPARISON.search(text):
        raise ValueError("price comparison is not allowed in AI text")


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
    """모델 응답 문자열을 검증해 계약 형식으로 만든다. 문제가 있으면 ValueError.

    모델 응답은 {"evidence_ids": [...], "cautions": [...]}만 허용한다. 요약은 받지 않는다.
    """
    value = _load_json_object(raw)
    if set(value) != {"evidence_ids", "cautions"}:
        raise ValueError("unexpected keys")
    evidence_ids = _string_list(value["evidence_ids"])
    if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("invalid evidence ids")
    if not set(evidence_ids) <= set(analysis["evidence_ids"]):
        raise ValueError("unknown evidence id")
    cautions = _string_list(value["cautions"])
    if not 1 <= len(cautions) <= AI_CAUTIONS_MAX:
        raise ValueError("invalid caution count")
    for text in cautions:
        _check_text(text, analysis)
    return _response(analysis, fixed_summary(analysis), evidence_ids, _cautions(analysis, cautions), "ai")


def explain_analysis(analysis, generate=None):
    """analysis.schema.json 형식의 분석 결과를 explanation.schema.json 형식으로 설명한다.

    summary는 두 mode 모두 코드가 만든 고정 문장이다. mode=ai이면 cautions에
    검증을 통과한 모델의 확인 사항이 더해진다. generate가 없거나, 호출이 실패하거나,
    응답이 검증을 통과하지 못하면 mode=fallback.
    """
    fallback = fallback_explanation(analysis)
    if generate is None:
        return fallback
    try:
        raw = generate(prompts.EXPLAIN_SYSTEM, prompts.build_explain_prompt(analysis))
        return validate_explanation(raw, analysis)
    except Exception:  # 시간 초과·한도 초과·형식 오류 모두 기본 안내로 대체
        return fallback
