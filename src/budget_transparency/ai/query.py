"""자연어 질문 → 검색 조건. 조회·필터·정렬은 하지 않는다(search 모듈 담당).

options는 options.schema.json 형식({"agencies": [{id, name}], "items": [{id, name}]}).
generate는 (system, user) 문자열을 받아 모델의 응답 문자열을 돌려주는 함수다.
"""
import calendar
import json
import re
from datetime import date

from . import prompts

TEXT_MAX = 500
Q_MAX = 200
FILTER_KEYS = ("q", "agency_id", "item_id", "date_from", "date_to")

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_KOREAN_DATE = re.compile(r"\d+\s*(?:년|월|일)")
_FROM_WORDS = ("부터", "이후")
_TO_WORDS = ("까지", "이전")
# 조건이 아닌 낱말: 조사, 기간 표현, 요청 표현, 모든 구매 기록에 해당하는 일반 명사
_IGNORED = {
    "의", "을", "를", "은", "는", "이", "가", "에", "에서", "로", "으로", "과", "와", "도", "만",
    "부터", "이후", "까지", "이전", "사이", "동안",
    "보여줘", "보여", "줘", "알려줘", "알려", "찾아줘", "찾아", "검색해줘", "해줘", "좀",
    "구매", "내역", "기록", "가격", "단가", "목록", "조회", "검색", "비교",
}

W_FALLBACK = "기본 규칙으로 해석했습니다. 조건을 확인하고 필요하면 수정하세요."
W_AI_FAILED = "AI 조건 추출을 사용하지 못했습니다."
W_NO_OPTIONS = "기관·품목 목록이 없어 이름을 해석하지 못했습니다."
W_UNMATCHED = "기관·품목 목록에서 찾지 못한 낱말을 검색어로 사용했습니다: {}"
W_NOT_REFLECTED = "질문의 일부 낱말이 조건에 반영되지 않았습니다: {}"
W_TOO_LONG = "인식하지 못한 내용이 길어 검색어로 사용하지 않았습니다."
W_MANY_DATES = "날짜가 세 개 이상이라 기간을 해석하지 못했습니다."
W_SAME_NAME = "‘{name}’ 이름의 {label}이 여러 개라 하나로 정하지 않고 검색어로 사용했습니다. 여러 {label}이 검색될 수 있습니다."


def _norm(text):
    return re.sub(r"\s+", "", text).casefold()


def _hits(text, entries):
    """이름이나 ID가 질문에 그대로 나온 항목."""
    plain = _norm(text)
    return [e for e in entries if _norm(e["name"]) in plain or _norm(e["id"]) in plain]


def _candidates(hits):
    """'예시 물품'과 '다른 규격 예시 물품'처럼 포함 관계면 긴 이름만 남긴다."""
    return [
        e for e in hits
        if not any(o is not e and _norm(e["name"]) in _norm(o["name"]) and _norm(e["name"]) != _norm(o["name"]) for o in hits)
    ]


def _shared_name(candidates):
    """후보가 여러 개인데 이름이 모두 같으면 그 이름. 같은 품목명에 ID가 여러 개인 경우다."""
    if len(candidates) > 1 and len({_norm(e["name"]) for e in candidates}) == 1:
        return candidates[0]["name"]
    return None


def _pick_one(hits, label, warnings):
    """(ID, 검색어로 넘길 이름)을 돌려준다. 여러 개면 ID를 임의로 고르지 않는다."""
    candidates = _candidates(hits)
    if len(candidates) == 1:
        return candidates[0]["id"], None
    name = _shared_name(candidates)
    if name:
        warnings.append(W_SAME_NAME.format(name=name, label=label))
        return None, name
    if candidates:
        warnings.append(f"{label} 이름이 여러 개와 일치해 선택하지 않았습니다.")
    return None, None


def _leftover(text, entries, drop_korean_dates=False):
    """기관·품목 이름, 날짜, 조건이 아닌 낱말을 뺀 나머지. 인식하지 못한 내용이다."""
    names = [e[key] for e in _hits(text, entries) for key in ("name", "id")]
    for name in sorted(names, key=len, reverse=True):
        pattern = r"\s*".join(re.escape(ch) for ch in re.sub(r"\s+", "", name))
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = _DATE.sub(" ", text)
    if drop_korean_dates:
        text = _KOREAN_DATE.sub(" ", text)
    words = []
    for token in text.split():
        token = token.strip("?!.,~\"'()[]")
        if len(token) >= 3 and token[-1] in "을를":
            token = token[:-1]
        if token and token not in _IGNORED:
            words.append(token)
    return " ".join(words)


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


def _entries(options, key):
    return (options or {}).get(key, [])


def _fallback(text, options, warnings):
    filters = dict.fromkeys(FILTER_KEYS)
    if options is None:
        warnings.append(W_NO_OPTIONS)
    agencies, items = _entries(options, "agencies"), _entries(options, "items")
    filters["agency_id"], agency_name = _pick_one(_hits(text, agencies), "기관", warnings)
    filters["item_id"], item_name = _pick_one(_hits(text, items), "품목", warnings)
    filters["date_from"], filters["date_to"] = _dates(text, warnings)
    # 인식하지 못한 낱말과 ID를 하나로 정하지 못한 이름은 버리지 않고 검색어로 넘겨,
    # 전체 목록을 검색 결과로 오해하지 않게 한다.
    rest = _leftover(text, agencies + items)
    query = " ".join(part for part in (agency_name, item_name, rest) if part)
    if query:
        if len(query) <= Q_MAX:
            filters["q"] = query
            if rest:
                warnings.append(W_UNMATCHED.format(rest))
        else:
            warnings.append(W_TOO_LONG)
    warnings.append(W_FALLBACK)
    return {"filters": filters, "mode": "fallback", "warnings": warnings}


def _grounded_date(value, text, end):
    """날짜가 질문에 적힌 내용과 연결될 때만 통과시킨다.

    허용: YYYY-MM-DD가 질문에 그대로 있음 / 'Y년 M월 D일' / 'Y년 M월'(시작=1일, 끝=말일) /
    'Y년'만 있음(시작=1월 1일, 끝=12월 31일).
    """
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("invalid date")
    parsed = date.fromisoformat(value)
    if value in text:
        return value
    y, m, d = parsed.year, parsed.month, parsed.day
    if not re.search(rf"(?<!\d){y}\s*년", text):
        raise ValueError("year not in question")
    if re.search(rf"(?<!\d)0?{m}\s*월", text):
        if re.search(rf"(?<!\d)0?{d}\s*일", text):
            return value
        edge = calendar.monthrange(y, m)[1] if end else 1
        if d == edge and not re.search(r"\d\s*일", text):
            return value
    elif not re.search(r"\d\s*월", text) and (m, d) == ((12, 31) if end else (1, 1)):
        return value
    raise ValueError("date not grounded in question")


def validate_filters(raw, text, options):
    """모델 응답 문자열을 검증한다. 문제가 있으면 ValueError."""
    if not isinstance(raw, str):
        raise ValueError("response is not text")
    body = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", body, re.DOTALL)
    value = json.loads(fenced.group(1) if fenced else body)
    if not isinstance(value, dict) or set(value) != set(FILTER_KEYS):
        raise ValueError("unexpected keys")
    filters = dict.fromkeys(FILTER_KEYS)
    shared_names = []
    for key, entries in (("agency_id", _entries(options, "agencies")), ("item_id", _entries(options, "items"))):
        hits = _hits(text, entries)
        candidates = _candidates(hits)
        shared = _shared_name(candidates)
        if shared:
            shared_names.append(shared)
        if value[key] is not None:
            # 목록에 있는 ID라도 그 이름이나 ID가 질문에 나오지 않았으면 추측으로 본다.
            if value[key] not in {e["id"] for e in hits}:
                raise ValueError(f"{key} not grounded in question")
            # 같은 이름의 ID가 여러 개면 모델이 하나를 임의로 고른 것이다.
            if shared and value[key] in {e["id"] for e in candidates}:
                raise ValueError(f"{key} is ambiguous")
            filters[key] = value[key]
    q = value["q"]
    if q is not None:
        if not isinstance(q, str) or not q.strip() or len(q.strip()) > Q_MAX:
            raise ValueError("invalid q")
        q = q.strip()
        if _norm(q) not in _norm(text):
            raise ValueError("q not in question")
        filters["q"] = q
    for name in shared_names:  # ID를 정할 수 없는 이름은 검색어에 남아 있어야 한다
        if filters["q"] is None or _norm(name) not in _norm(filters["q"]):
            raise ValueError("ambiguous name dropped")
    filters["date_from"] = _grounded_date(value["date_from"], text, end=False)
    filters["date_to"] = _grounded_date(value["date_to"], text, end=True)
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
        except Exception:  # 시간 초과·한도 초과·형식 오류 모두 기본 규칙으로 대체
            warnings.append(W_AI_FAILED)
        else:
            # 같은 이름의 ID가 여러 개라 검색어로 넘긴 경우, AI 결과에도 같은 경고를 붙인다.
            for key, label in (("agencies", "기관"), ("items", "품목")):
                name = _shared_name(_candidates(_hits(text, _entries(options, key))))
                if name:
                    warnings.append(W_SAME_NAME.format(name=name, label=label))
            if filters["q"] is None:
                has_dates = bool(filters["date_from"] or filters["date_to"])
                rest = _leftover(text, _entries(options, "agencies") + _entries(options, "items"), has_dates)
                if rest:
                    warnings.append(W_NOT_REFLECTED.format(rest[:Q_MAX]))
            return {"filters": filters, "mode": "ai", "warnings": warnings}
    return _fallback(text, options, warnings)
