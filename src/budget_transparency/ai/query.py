"""자연어 질문 → 검색 조건. 조회·필터·정렬은 하지 않는다(search 모듈 담당).

options는 options.schema.json 형식({"agencies": [{id, name}], "items": [{id, name}]}).
generate는 (system, user) 문자열을 받아 모델의 응답 문자열을 돌려주는 함수다.
"""
import json
import re
from datetime import date

from . import prompts

TEXT_MAX = 500
Q_MAX = 200
FILTER_KEYS = ("q", "agency_id", "item_id", "date_from", "date_to")

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_FROM_WORDS = ("부터", "이후")
_TO_WORDS = ("까지", "이전")

W_FALLBACK = "기본 규칙으로 해석했습니다. 조건을 확인하고 필요하면 수정하세요."
W_AI_FAILED = "AI 조건 추출을 사용하지 못했습니다."
W_NO_OPTIONS = "기관·품목 목록이 없어 이름을 해석하지 못했습니다."
W_NO_MATCH = "등록된 기관·품목과 일치하는 이름을 찾지 못해 입력 문장을 검색어로 사용합니다."
W_TOO_LONG = "입력이 길어 검색어로 사용하지 않았습니다."
W_MANY_DATES = "날짜가 세 개 이상이라 기간을 해석하지 못했습니다."


def _norm(text):
    return re.sub(r"\s+", "", text).casefold()


def _match_one(text, entries, label, warnings):
    """이름이 질문에 그대로 나온 항목만 찾는다. 여러 개면 고르지 않고 null."""
    plain = _norm(text)
    hits = [e for e in entries if _norm(e["name"]) in plain or _norm(e["id"]) in plain]
    # '예시 물품'과 '다른 규격 예시 물품'처럼 포함 관계면 긴 이름만 남긴다.
    hits = [
        e for e in hits
        if not any(o is not e and _norm(e["name"]) in _norm(o["name"]) and _norm(e["name"]) != _norm(o["name"]) for o in hits)
    ]
    if len(hits) == 1:
        return hits[0]["id"]
    if len(hits) > 1:
        warnings.append(f"{label} 이름이 여러 개와 일치해 선택하지 않았습니다.")
    return None


def _dates(text, warnings):
    found = []
    for token in _DATE.findall(text):
        try:
            found.append(date.fromisoformat(token))
        except ValueError:
            warnings.append(f"잘못된 날짜를 제외했습니다: {token}")
    if not found:
        return None, None
    if len(found) > 2:
        warnings.append(W_MANY_DATES)
        return None, None
    if len(found) == 2:
        return min(found).isoformat(), max(found).isoformat()
    day = found[0].isoformat()
    if any(word in text for word in _FROM_WORDS):
        return day, None
    if any(word in text for word in _TO_WORDS):
        return None, day
    return day, day


def _fallback(text, options, warnings):
    filters = dict.fromkeys(FILTER_KEYS)
    if options is None:
        warnings.append(W_NO_OPTIONS)
    else:
        filters["agency_id"] = _match_one(text, options.get("agencies", []), "기관", warnings)
        filters["item_id"] = _match_one(text, options.get("items", []), "품목", warnings)
    filters["date_from"], filters["date_to"] = _dates(text, warnings)
    if all(value is None for value in filters.values()):
        if len(text) <= Q_MAX:
            filters["q"] = text
            warnings.append(W_NO_MATCH)
        else:
            warnings.append(W_TOO_LONG)
    warnings.append(W_FALLBACK)
    return {"filters": filters, "mode": "fallback", "warnings": warnings}


def _valid_date(value, text):
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("invalid date")
    parsed = date.fromisoformat(value)
    if str(parsed.year) not in text:  # 질문에 없는 연도는 추측으로 본다
        raise ValueError("date not grounded in question")
    return parsed.isoformat()


def validate_filters(raw, text, options):
    """모델 응답 문자열을 검증한다. 문제가 있으면 ValueError."""
    if not isinstance(raw, str):
        raise ValueError("response is not text")
    body = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", body, re.DOTALL)
    value = json.loads(fenced.group(1) if fenced else body)
    if not isinstance(value, dict) or set(value) != set(FILTER_KEYS):
        raise ValueError("unexpected keys")
    known = {
        "agency_id": {e["id"] for e in (options or {}).get("agencies", [])},
        "item_id": {e["id"] for e in (options or {}).get("items", [])},
    }
    filters = dict.fromkeys(FILTER_KEYS)
    for key, ids in known.items():
        if value[key] is not None:
            if value[key] not in ids:
                raise ValueError(f"unknown {key}")
            filters[key] = value[key]
    q = value["q"]
    if q is not None:
        if not isinstance(q, str) or not q.strip() or len(q.strip()) > Q_MAX:
            raise ValueError("invalid q")
        q = q.strip()
        if _norm(q) not in _norm(text):
            raise ValueError("q not in question")
        filters["q"] = q
    filters["date_from"] = _valid_date(value["date_from"], text)
    filters["date_to"] = _valid_date(value["date_to"], text)
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise ValueError("reversed dates")
    return filters


def parse_query(text, options=None, generate=None):
    """질문을 query.schema.json 형식의 검색 조건으로 바꾼다.

    공백 제거 후 1~500자가 아니면 ValueError(서버에서 400으로 처리).
    generate가 없거나, 호출이 실패하거나, 응답이 검증을 통과하지 못하면 mode=fallback.
    """
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    text = text.strip()
    if not 1 <= len(text) <= TEXT_MAX:
        raise ValueError("text must be 1-500 characters")
    warnings = []
    if generate is not None:
        try:
            raw = generate(prompts.QUERY_SYSTEM, prompts.build_query_prompt(text, options))
            filters = validate_filters(raw, text, options)
            return {"filters": filters, "mode": "ai", "warnings": warnings}
        except Exception:  # 시간 초과·한도 초과·형식 오류 모두 기본 규칙으로 대체
            warnings.append(W_AI_FAILED)
    return _fallback(text, options, warnings)
