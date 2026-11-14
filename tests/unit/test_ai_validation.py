"""C(AI) 함수 검사. 모델 응답은 고정된 가짜 응답으로 재현하며 실제 모델을 호출하지 않는다."""
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from budget_transparency.ai import gemini, prompts  # noqa: E402
from budget_transparency.ai.explain import available_checks, explain_analysis  # noqa: E402
from budget_transparency.ai.query import parse_query  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/contracts-v1"
ANALYSIS_FILES = [
    "analysis.json",
    "analysis-market.json",
    "analysis-insufficient.json",
    "analysis-unknown.json",
    "analysis-no-market.json",
    "analysis-unavailable.json",
]


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def validator(name):
    schema = json.loads((ROOT / "docs/contracts" / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


EXPLANATION = validator("explanation.schema.json")
QUERY = validator("query.schema.json")
OPTIONS = read("options.json")
# 실제 시연 데이터처럼 같은 품목명에 ID가 여러 개인 경우(합성).
DUP_OPTIONS = {
    "agencies": OPTIONS["agencies"],
    "items": OPTIONS["items"] + [{"id": f"dup-{n}", "name": "중복 품목"} for n in (1, 2, 3)],
}


def fake(response):
    """항상 같은 응답을 돌려주는 가짜 모델."""
    def generate(system, user):
        return response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    return generate


def failing(error):
    def generate(system, user):
        raise error
    return generate


GOOD_EXPLANATION = {"evidence_ids": ["demo-A", "demo-B"], "caution_ids": ["installation", "excluded"]}


class ExplainFallbackTests(unittest.TestCase):
    def test_every_fixture_gets_valid_fallback(self):
        for name in ANALYSIS_FILES:
            with self.subTest(name=name):
                analysis = read(name)
                result = explain_analysis(analysis)
                EXPLANATION.validate(result)
                self.assertEqual(result["mode"], "fallback")
                for key in ("dataset_version", "record_id", "comparison_type"):
                    self.assertEqual(result[key], analysis[key])
                self.assertEqual(result["evidence_ids"], analysis["evidence_ids"])
                self.assertTrue(any("합성" in c for c in result["cautions"]))
                self.assertNotRegex(result["summary"], r"\d")

    def test_non_comparable_says_not_calculated(self):
        for name in ANALYSIS_FILES[2:]:
            with self.subTest(name=name):
                self.assertIn("계산하지 않았습니다", explain_analysis(read(name))["summary"])

    def test_insufficient_uses_agreed_sentence(self):
        result = explain_analysis(read("analysis-insufficient.json"))
        self.assertEqual(result["summary"], "비교 자료가 부족해 가격 차이를 계산하지 않았습니다.")

    def test_zero_difference_does_not_claim_difference(self):
        analysis = read("analysis.json")
        analysis.update(difference="0", difference_pct="0.00")
        self.assertNotIn("차이가 있습니다", explain_analysis(analysis)["summary"])

    def test_synthetic_caution_added_when_limitations_empty(self):
        analysis = read("analysis.json")
        analysis["limitations"] = []
        self.assertTrue(any("합성" in c for c in explain_analysis(analysis)["cautions"]))


class ExplainAiValidationTests(unittest.TestCase):
    def setUp(self):
        self.analysis = read("analysis.json")

    def assert_fallback(self, generate, analysis=None):
        analysis = analysis or self.analysis
        result = explain_analysis(analysis, generate)
        EXPLANATION.validate(result)
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result, explain_analysis(analysis))
        return result

    def test_valid_selection_is_used(self):
        fallback = explain_analysis(self.analysis)
        result = explain_analysis(self.analysis, fake(GOOD_EXPLANATION))
        EXPLANATION.validate(result)
        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["evidence_ids"], ["demo-A", "demo-B"])
        self.assertEqual(result["summary"], fallback["summary"])  # 요약은 모델이 쓰지 않는다
        checks = available_checks(self.analysis)
        self.assertEqual(result["cautions"], fallback["cautions"] + [checks["installation"], checks["excluded"]])

    def test_every_output_sentence_comes_from_code(self):
        for name in ANALYSIS_FILES:
            with self.subTest(name=name):
                analysis = read(name)
                checks = available_checks(analysis)
                response = {"evidence_ids": [analysis["record_id"]], "caution_ids": list(checks)[:3]}
                result = explain_analysis(analysis, fake(response))
                EXPLANATION.validate(result)
                self.assertEqual(result["mode"], "ai")
                allowed = set(checks.values()) | set(explain_analysis(analysis)["cautions"])
                self.assertLessEqual(set(result["cautions"]), allowed)

    def test_checks_only_ask_to_confirm(self):
        for name in ANALYSIS_FILES:
            for text in available_checks(read(name)).values():
                with self.subTest(text=text):
                    self.assertTrue(text.endswith("확인하세요."))
                    self.assertNotRegex(text, r"\d|때문|무료|확인되었")

    def test_checks_depend_on_analysis(self):
        self.assertIn("excluded", available_checks(self.analysis))
        self.assertNotIn("market", available_checks(self.analysis))
        market = available_checks(read("analysis-market.json"))
        self.assertIn("market", market)
        self.assertNotIn("excluded", market)

    def test_code_fenced_json_is_accepted(self):
        raw = "```json\n" + json.dumps(GOOD_EXPLANATION, ensure_ascii=False) + "\n```"
        self.assertEqual(explain_analysis(self.analysis, fake(raw))["mode"], "ai")

    def test_free_text_is_never_shown(self):
        # 리뷰 회귀(1~3차): 모델이 쓴 문장은 어떤 자리에 넣어도 화면에 나가지 않는다.
        sentences = [
            "배송비는 무료입니다.",                      # 3차: 확인되지 않은 사실
            "계약 조건은 모두 확인되었습니다.",            # 3차: 확인되지 않은 사실
            "가격 차이는 배송비 때문입니다.",              # 3차: 차이의 원인
            "예시기관 A의 단가는 120000원입니다.",         # 2차: 역할이 바뀐 숫자
            "기준보다 높지 않습니다.",                    # 2차: 부정문
            "기준보다 적습니다.",                        # 2차: 목록에 없던 표현
            "기준보다 낮습니다.",                        # 1차: 반대 방향
            "이 구매는 예산 낭비이며 비리가 의심됩니다.",
            "출처: https://example.com",
            "설치비 포함 여부를 확인하세요.",              # 문제없는 문장도 모델이 쓴 것은 받지 않는다
        ]
        for name in ("analysis-unknown.json", "analysis.json"):
            analysis = read(name)
            evidence = [analysis["record_id"]]
            for text in sentences:
                responses = {
                    "as caution id": {"evidence_ids": evidence, "caution_ids": [text]},
                    "mixed with valid id": {"evidence_ids": evidence, "caution_ids": ["tax", text]},
                    "as cautions": {"evidence_ids": evidence, "cautions": [text]},
                    "extra cautions key": {"evidence_ids": evidence, "caution_ids": ["tax"], "cautions": [text]},
                    "as summary": {"evidence_ids": evidence, "caution_ids": ["tax"], "summary": text},
                    "as evidence id": {"evidence_ids": [text], "caution_ids": ["tax"]},
                }
                for label, response in responses.items():
                    with self.subTest(name=name, text=text, label=label):
                        result = self.assert_fallback(fake(response), analysis)
                        self.assertNotIn(text, json.dumps(result, ensure_ascii=False))

    def test_rejected_responses_fall_back(self):
        cases = {
            "unknown evidence id": dict(GOOD_EXPLANATION, evidence_ids=["demo-A", "demo-Z"]),
            "empty evidence": dict(GOOD_EXPLANATION, evidence_ids=[]),
            "duplicate evidence": dict(GOOD_EXPLANATION, evidence_ids=["demo-A", "demo-A"]),
            "missing key": {"caution_ids": ["tax"]},
            "extra key": dict(GOOD_EXPLANATION, source_url="x"),
            "no selection": dict(GOOD_EXPLANATION, caution_ids=[]),
            "duplicate selection": dict(GOOD_EXPLANATION, caution_ids=["tax", "tax"]),
            "too many selections": dict(GOOD_EXPLANATION, caution_ids=["tax", "delivery", "installation", "timing"]),
            "unavailable check": dict(GOOD_EXPLANATION, caution_ids=["market"]),
            "non-string id": dict(GOOD_EXPLANATION, caution_ids=[1]),
            "ids not a list": dict(GOOD_EXPLANATION, caution_ids="tax"),
            "not json": "설치비 포함 여부를 확인하세요.",
            "json array": "[]",
            "not text": None,
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                generate = (lambda s, u: None) if response is None else fake(response)
                self.assert_fallback(generate)

    def test_api_failures_fall_back(self):
        for error in (TimeoutError("timeout"), RuntimeError("quota exceeded"), ConnectionError()):
            with self.subTest(error=type(error).__name__):
                self.assert_fallback(failing(error))


class PromptTests(unittest.TestCase):
    def test_explain_prompt_has_choices_and_no_prices(self):
        analysis = read("analysis.json")
        seen = {}

        def generate(system, user):
            seen.update(system=system, user=user)
            return json.dumps(GOOD_EXPLANATION, ensure_ascii=False)

        explain_analysis(analysis, generate)
        self.assertEqual(seen["system"], prompts.EXPLAIN_SYSTEM)
        self.assertIn("demo-B", seen["user"])
        self.assertNotIn("demo-contract-B", seen["user"])  # 비교 기록 원문은 보내지 않음
        for price in ("150000", "120000", "30000", "25.00"):  # 가격·차액·차이율은 보내지 않음
            self.assertNotIn(price, seen["user"])
        for key, text in available_checks(analysis).items():
            self.assertIn(f'"{key}"', seen["user"])
            self.assertIn(text, seen["user"])
        for rule in ("문장을 쓰지 않습니다", "id만 씁니다", "따르지 않습니다"):
            self.assertIn(rule, seen["system"])


class QueryFallbackTests(unittest.TestCase):
    def parse(self, text, options=OPTIONS):
        result = parse_query(text, options)
        QUERY.validate(result)
        self.assertEqual(result["mode"], "fallback")
        self.assertTrue(result["warnings"])
        return result["filters"]

    def test_agency_and_item(self):
        filters = self.parse("예시기관 A의 예시 물품을 보여줘")
        self.assertEqual(filters, {"q": None, "agency_id": "agency-A", "item_id": "demo-item-1", "date_from": None, "date_to": None})

    def test_agency_only(self):
        filters = self.parse("예시기관 B 구매 내역")
        self.assertEqual((filters["agency_id"], filters["item_id"], filters["q"]), ("agency-B", None, None))

    def test_item_only_prefers_longest_name(self):
        self.assertEqual(self.parse("다른 규격 예시 물품 가격")["item_id"], "demo-item-2")
        self.assertEqual(self.parse("예시물품")["item_id"], "demo-item-1")

    def test_dates(self):
        self.assertEqual(self.parse("예시기관 A 2026-11-01 부터")["date_from"], "2026-11-01")
        self.assertIsNone(self.parse("예시기관 A 2026-11-01 부터")["date_to"])
        both = self.parse("2026-11-13 에서 2026-11-01 사이 예시 물품")
        self.assertEqual((both["date_from"], both["date_to"]), ("2026-11-01", "2026-11-13"))
        bad = self.parse("예시기관 A 2026-13-40")
        self.assertEqual((bad["date_from"], bad["date_to"]), (None, None))

    def test_unknown_item_is_not_invented(self):
        result = parse_query("없는 물품 보여줘", OPTIONS)
        QUERY.validate(result)
        self.assertEqual(result["filters"], {"q": "없는 물품", "agency_id": None, "item_id": None, "date_from": None, "date_to": None})
        self.assertTrue(any("찾지 못한" in w and "없는 물품" in w for w in result["warnings"]))

    def test_unrecognized_word_is_kept_as_search_term(self):
        # 리뷰 회귀: '노트북'이 조용히 빠져 기관 전체 목록을 노트북 결과로 오해하면 안 된다.
        result = parse_query("예시기관 A의 노트북", OPTIONS)
        QUERY.validate(result)
        self.assertEqual(result["filters"], {"q": "노트북", "agency_id": "agency-A", "item_id": None, "date_from": None, "date_to": None})
        self.assertTrue(any("노트북" in w for w in result["warnings"]))
        self.assertEqual(self.parse("예시기관 A의 노트북을 보여줘")["q"], "노트북")

    def test_recognized_question_has_no_search_term(self):
        for text in ("예시기관 A 구매 내역", "예시기관 A의 예시 물품을 2026-11-01 부터 보여줘"):
            with self.subTest(text=text):
                self.assertIsNone(self.parse(text)["q"])

    def test_same_item_name_with_many_ids_becomes_search_term(self):
        # 리뷰 회귀: 같은 품목명에 ID가 여러 개면 하나를 고르지 않고 이름을 검색어로 넘긴다.
        result = parse_query("예시기관 A의 중복 품목", DUP_OPTIONS)
        QUERY.validate(result)
        self.assertEqual(result["filters"], {"q": "중복 품목", "agency_id": "agency-A", "item_id": None, "date_from": None, "date_to": None})
        self.assertTrue(any("중복 품목" in w and "여러 품목이 검색될 수 있습니다" in w for w in result["warnings"]))
        self.assertFalse(any("찾지 못한" in w for w in result["warnings"]))
        self.assertEqual(self.parse("중복품목 보여줘", DUP_OPTIONS)["q"], "중복 품목")

    def test_same_item_name_keeps_other_conditions(self):
        filters = self.parse("예시기관 A의 중복 품목 2026-11-01 부터", DUP_OPTIONS)
        self.assertEqual(filters, {"q": "중복 품목", "agency_id": "agency-A", "item_id": None, "date_from": "2026-11-01", "date_to": None})
        with_word = self.parse("예시기관 A의 중복 품목 흑백", DUP_OPTIONS)
        self.assertEqual((with_word["item_id"], with_word["q"]), (None, "중복 품목 흑백"))

    def test_unique_names_still_resolve_to_ids(self):
        filters = self.parse("예시기관 A의 예시 물품", DUP_OPTIONS)
        self.assertEqual((filters["agency_id"], filters["item_id"], filters["q"]), ("agency-A", "demo-item-1", None))
        self.assertEqual(self.parse("dup-2 보여줘", DUP_OPTIONS)["item_id"], "dup-2")  # ID를 직접 쓴 경우

    def test_without_options_ids_stay_null(self):
        filters = self.parse("예시기관 A의 예시 물품", options=None)
        self.assertEqual((filters["agency_id"], filters["item_id"]), (None, None))

    def test_text_length_limits(self):
        for text in ("", "   ", "가" * 501, None):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_query(text, OPTIONS)


class QueryAiValidationTests(unittest.TestCase):
    TEXT = "예시기관 A의 예시 물품을 2026-11-01 부터 보여줘"
    GOOD = {"q": None, "agency_id": "agency-A", "item_id": "demo-item-1", "date_from": "2026-11-01", "date_to": None}

    def test_valid_response_is_used(self):
        result = parse_query(self.TEXT, OPTIONS, fake(self.GOOD))
        QUERY.validate(result)
        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["filters"], self.GOOD)

    def test_rejected_responses_fall_back(self):
        cases = {
            "unknown agency": dict(self.GOOD, agency_id="agency-Z"),
            "unknown item": dict(self.GOOD, item_id="notebook"),
            "guessed year": dict(self.GOOD, date_from="2025-01-01"),
            "bad date": dict(self.GOOD, date_from="2026-13-40"),
            "reversed dates": dict(self.GOOD, date_from="2026-11-13", date_to="2026-11-01"),
            "q not in question": dict(self.GOOD, q="노트북"),
            "extra key": dict(self.GOOD, sql="DROP TABLE purchases"),
            "missing key": {"agency_id": "agency-A"},
            "not json": "SELECT * FROM purchases",
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                result = parse_query(self.TEXT, OPTIONS, fake(response))
                QUERY.validate(result)
                self.assertEqual(result["mode"], "fallback")
                self.assertEqual(result["filters"]["agency_id"], "agency-A")
                self.assertTrue(any("AI" in w for w in result["warnings"]))

    def test_api_failures_fall_back(self):
        for error in (TimeoutError("timeout"), RuntimeError("quota exceeded")):
            with self.subTest(error=type(error).__name__):
                result = parse_query(self.TEXT, OPTIONS, failing(error))
                QUERY.validate(result)
                self.assertEqual(result["mode"], "fallback")
                self.assertNotIn("quota", " ".join(result["warnings"]))

    def test_agency_and_date_not_in_question_fall_back(self):
        # 리뷰 회귀: 목록에 있는 ID, 질문과 같은 연도라도 질문과 연결되지 않으면 통과시키지 않는다.
        text = "예시기관 A 2026-11-01"
        base = {"q": None, "agency_id": "agency-A", "item_id": None, "date_from": "2026-11-01", "date_to": "2026-11-01"}
        cases = {
            "other agency and date": dict(base, agency_id="agency-B", date_to="2026-12-31"),
            "other agency": dict(base, agency_id="agency-B"),
            "other date": dict(base, date_to="2026-12-31"),
            "item not mentioned": dict(base, item_id="demo-item-1"),
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                result = parse_query(text, OPTIONS, fake(response))
                QUERY.validate(result)
                self.assertEqual(result["mode"], "fallback")
                self.assertEqual(result["filters"], base)
        self.assertEqual(parse_query(text, OPTIONS, fake(base))["mode"], "ai")

    def test_korean_dates_must_match_question(self):
        text = "예시기관 A 2026년 11월"
        base = {"q": None, "agency_id": "agency-A", "item_id": None, "date_from": "2026-11-01", "date_to": "2026-11-30"}
        result = parse_query(text, OPTIONS, fake(base))
        self.assertEqual((result["mode"], result["warnings"]), ("ai", []))
        for label, response in {
            "other month": dict(base, date_from="2026-12-01", date_to="2026-12-31"),
            "day not in question": dict(base, date_from="2026-11-05"),
            "other year": dict(base, date_from="2025-11-01"),
        }.items():
            with self.subTest(label=label):
                self.assertEqual(parse_query(text, OPTIONS, fake(response))["mode"], "fallback")
        whole_year = dict(base, date_from="2026-01-01", date_to="2026-12-31")
        self.assertEqual(parse_query("예시기관 A 2026년", OPTIONS, fake(whole_year))["mode"], "ai")
        self.assertEqual(parse_query("예시기관 A 2026년", OPTIONS, fake(base))["mode"], "fallback")

    def test_dropped_word_is_warned_in_ai_mode(self):
        # 리뷰 회귀: 모델이 '노트북'을 조건에서 빼면 경고한다.
        text = "예시기관 A의 노트북"
        base = {"q": None, "agency_id": "agency-A", "item_id": None, "date_from": None, "date_to": None}
        dropped = parse_query(text, OPTIONS, fake(base))
        QUERY.validate(dropped)
        self.assertEqual(dropped["mode"], "ai")
        self.assertTrue(any("노트북" in w for w in dropped["warnings"]))
        kept = parse_query(text, OPTIONS, fake(dict(base, q="노트북")))
        self.assertEqual((kept["mode"], kept["filters"]["q"], kept["warnings"]), ("ai", "노트북", []))

    def test_model_cannot_pick_one_of_same_named_items(self):
        # 리뷰 회귀: 모델이 같은 이름의 ID 중 하나를 고르거나 이름을 빼면 기본 규칙으로 대체한다.
        text = "예시기관 A의 중복 품목"
        expected = {"q": "중복 품목", "agency_id": "agency-A", "item_id": None, "date_from": None, "date_to": None}
        for label, response in {
            "picked one id": dict(expected, q=None, item_id="dup-1"),
            "picked id and q": dict(expected, item_id="dup-2"),
            "dropped name": dict(expected, q=None),
        }.items():
            with self.subTest(label=label):
                result = parse_query(text, DUP_OPTIONS, fake(response))
                QUERY.validate(result)
                self.assertEqual((result["mode"], result["filters"]), ("fallback", expected))
                self.assertTrue(any("여러 품목이 검색될 수 있습니다" in w for w in result["warnings"]))
        result = parse_query(text, DUP_OPTIONS, fake(expected))
        QUERY.validate(result)
        self.assertEqual((result["mode"], result["filters"]), ("ai", expected))
        # 리뷰 회귀: 모델이 올바르게 답한 AI 경로에서도 같은 경고를 표시한다.
        self.assertEqual(result["warnings"], ["‘중복 품목’ 이름의 품목이 여러 개라 하나로 정하지 않고 검색어로 사용했습니다. 여러 품목이 검색될 수 있습니다."])
        fallback = parse_query(text, DUP_OPTIONS)
        self.assertIn(result["warnings"][0], fallback["warnings"])

    def test_no_same_name_warning_for_unique_item_in_ai_mode(self):
        response = {"q": None, "agency_id": "agency-A", "item_id": "demo-item-1", "date_from": None, "date_to": None}
        result = parse_query("예시기관 A의 예시 물품", DUP_OPTIONS, fake(response))
        self.assertEqual((result["mode"], result["warnings"]), ("ai", []))

    def test_ids_rejected_without_options(self):
        self.assertEqual(parse_query(self.TEXT, None, fake(self.GOOD))["mode"], "fallback")


class FakeResponse:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def model_reply(text):
    """Gemini REST 응답 모양으로 감싼 가짜 응답."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


class GeminiCallTests(unittest.TestCase):
    """실제 네트워크 호출 없이 요청 모양·오류 처리·키 비노출을 검사한다."""
    KEY = "test-key-not-real"

    def make(self, reply=None, error=None, model="test-model"):
        seen = {}

        def opener(request, timeout):
            seen.update(request=request, timeout=timeout)
            if error is not None:
                raise error
            return FakeResponse(reply)

        return gemini.make_generate(api_key=self.KEY, model=model, opener=opener), seen

    def test_request_shape_and_key_only_in_header(self):
        generate, seen = self.make(model_reply('{"ok": true}'))
        self.assertEqual(generate("지시문", "자료"), '{"ok": true}')
        request = seen["request"]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/models/test-model:generateContent"))
        self.assertNotIn(self.KEY, request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), self.KEY)
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn(self.KEY, request.data.decode("utf-8"))
        self.assertEqual(body["system_instruction"]["parts"][0]["text"], "지시문")
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "자료")
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(seen["timeout"], gemini.TIMEOUT_SECONDS)

    def test_missing_key_or_model_gives_none(self):
        self.assertIsNone(gemini.make_generate(api_key="", model="test-model"))
        self.assertIsNone(gemini.make_generate(api_key=self.KEY, model=" "))
        analysis = read("analysis.json")
        self.assertEqual(explain_analysis(analysis, gemini.make_generate(api_key="", model=""))["mode"], "fallback")

    def test_invalid_model_id_is_rejected(self):
        for model in ("a/b", "x?key=1", "모델"):
            with self.subTest(model=model):
                with self.assertRaises(gemini.GeminiError):
                    gemini.make_generate(api_key=self.KEY, model=model)

    def test_failures_raise_without_leaking_key(self):
        import urllib.error
        cases = {
            "quota": urllib.error.HTTPError("https://example.invalid/?key=" + self.KEY, 429, "Too Many Requests", None, None),
            "server": urllib.error.HTTPError("https://example.invalid", 500, self.KEY, None, None),
            "network": urllib.error.URLError("unreachable " + self.KEY),
            "timeout": TimeoutError("timed out"),
        }
        for label, error in cases.items():
            with self.subTest(label=label):
                generate, _ = self.make(error=error)
                with self.assertRaises(gemini.GeminiError) as caught:
                    generate("지시문", "자료")
                self.assertNotIn(self.KEY, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_unusable_responses_raise(self):
        replies = [b"not json", {}, {"candidates": []}, {"candidates": [{"finishReason": "SAFETY"}]},
                   {"candidates": [{"content": {"parts": [{"text": "  "}]}}]},
                   {"promptFeedback": {"blockReason": "SAFETY"}}]
        for reply in replies:
            with self.subTest(reply=reply):
                generate, _ = self.make(reply)
                with self.assertRaises(gemini.GeminiError):
                    generate("지시문", "자료")

    def test_connected_functions_use_model_and_fall_back(self):
        analysis = read("analysis.json")
        good, seen = self.make(model_reply(json.dumps(GOOD_EXPLANATION)))
        result = explain_analysis(analysis, good)
        EXPLANATION.validate(result)
        self.assertEqual(result["mode"], "ai")
        sent = seen["request"].data.decode("utf-8")
        for price in ("150000", "120000"):  # 가격은 모델에 보내지 않는다
            self.assertNotIn(price, sent)
        bad, _ = self.make(model_reply("배송비는 무료입니다."))
        self.assertEqual(explain_analysis(analysis, bad), explain_analysis(analysis))
        import urllib.error
        down, _ = self.make(error=urllib.error.HTTPError("https://example.invalid", 429, "quota", None, None))
        self.assertEqual(explain_analysis(analysis, down)["mode"], "fallback")
        query = parse_query("예시기관 A의 예시 물품", OPTIONS, down)
        QUERY.validate(query)
        self.assertEqual((query["mode"], query["filters"]["agency_id"]), ("fallback", "agency-A"))
        self.assertNotIn(self.KEY, json.dumps(query, ensure_ascii=False))


class GeminiRedirectTests(unittest.TestCase):
    """리뷰 회귀: 리디렉션을 따라가 키 헤더가 다른 호스트로 전달되면 안 된다. 로컬 서버 두 개로 확인한다."""
    KEY = "test-key-not-real"

    def serve(self, handler):
        import http.server
        import threading
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_redirect_is_refused_and_key_not_forwarded(self):
        import http.server
        received = {"other": [], "first": []}

        class Other(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received["other"].append(dict(self.headers))
                body = json.dumps(model_reply('{"stolen": true}')).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST

            def log_message(self, *args):
                pass

        other = self.serve(Other)
        target = f"http://localhost:{other.server_port}/elsewhere"  # 다른 호스트 이름·포트

        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                class First(http.server.BaseHTTPRequestHandler):
                    def do_POST(self):
                        received["first"].append(self.headers.get("x-goog-api-key"))
                        self.rfile.read(int(self.headers.get("Content-Length", 0)))
                        self.send_response(code)
                        self.send_header("Location", target)
                        self.send_header("Content-Length", "0")
                        self.end_headers()

                    def log_message(self, *args):
                        pass

                first = self.serve(First)
                original = gemini.API_URL
                gemini.API_URL = f"http://127.0.0.1:{first.server_port}/v1beta/models/{{model}}:generateContent"
                try:
                    generate = gemini.make_generate(api_key=self.KEY, model="test-model", timeout=5)
                finally:
                    gemini.API_URL = original
                with self.assertRaises(gemini.GeminiError) as caught:
                    generate("지시문", "자료")
                self.assertNotIn(self.KEY, str(caught.exception))
                self.assertEqual(received["first"][-1], self.KEY)  # 원래 주소에는 키가 갔다
                self.assertEqual(received["other"], [])            # 리디렉션된 주소에는 요청 자체가 가지 않았다
                analysis = read("analysis.json")
                self.assertEqual(explain_analysis(analysis, generate), explain_analysis(analysis))
                self.assertEqual(received["other"], [])

    def test_plain_urllib_would_forward_the_key(self):
        # 이 테스트가 실제로 위험을 잡는지 확인: 기본 urlopen은 키 헤더를 리디렉션 대상에 보낸다.
        import http.server
        import urllib.request
        received = []

        class Other(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get("x-goog-api-key"))
                body = json.dumps(model_reply("{}")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_POST = do_GET

            def log_message(self, *args):
                pass

        other = self.serve(Other)

        class First(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(302)
                self.send_header("Location", f"http://localhost:{other.server_port}/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        first = self.serve(First)
        original = gemini.API_URL
        gemini.API_URL = f"http://127.0.0.1:{first.server_port}/v1beta/models/{{model}}:generateContent"
        try:
            unsafe = gemini.make_generate(api_key=self.KEY, model="test-model", timeout=5, opener=urllib.request.urlopen)
        finally:
            gemini.API_URL = original
        unsafe("지시문", "자료")
        self.assertEqual(received, [self.KEY])


class EnvFileTests(unittest.TestCase):
    def test_load_env_reads_file_without_overriding(self):
        import os
        import tempfile
        names = ("C_TEST_NEW", "C_TEST_EXISTING", "C_TEST_EMPTY", "C_TEST_QUOTED")
        saved = {name: os.environ.pop(name, None) for name in names}
        try:
            os.environ["C_TEST_EXISTING"] = "from-shell"
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / ".env"
                path.write_text("# 주석\nC_TEST_NEW=from-file\nC_TEST_EXISTING=from-file\nC_TEST_EMPTY=\nC_TEST_QUOTED=\"quoted value\"\nnot a setting\n", encoding="utf-8")
                loaded = gemini.load_env(path)
                self.assertEqual(gemini.load_env(Path(tmp) / "missing.env"), [])
            self.assertEqual(os.environ["C_TEST_NEW"], "from-file")
            self.assertEqual(os.environ["C_TEST_EXISTING"], "from-shell")
            self.assertEqual(os.environ["C_TEST_QUOTED"], "quoted value")
            self.assertNotIn("C_TEST_EMPTY", os.environ)
            self.assertEqual(loaded, ["C_TEST_NEW", "C_TEST_EXISTING", "C_TEST_QUOTED"])
        finally:
            for name, value in saved.items():
                os.environ.pop(name, None)
                if value is not None:
                    os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
