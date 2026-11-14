"""C(AI) 함수 검사. 모델 응답은 고정된 가짜 응답으로 재현하며 실제 모델을 호출하지 않는다."""
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from budget_transparency.ai import prompts  # noqa: E402
from budget_transparency.ai.explain import explain_analysis  # noqa: E402
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


def fake(response):
    """항상 같은 응답을 돌려주는 가짜 모델."""
    def generate(system, user):
        return response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    return generate


def failing(error):
    def generate(system, user):
        raise error
    return generate


GOOD_EXPLANATION = {
    "summary": "예시기관 A의 단가가 다른 기관 3곳의 기준 단가보다 높습니다. 계약 조건을 함께 확인하세요.",
    "evidence_ids": ["demo-A", "demo-B"],
    "cautions": ["설치비 포함 여부를 확인하세요."],
}


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

    def assert_fallback(self, generate):
        result = explain_analysis(self.analysis, generate)
        EXPLANATION.validate(result)
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result, explain_analysis(self.analysis))

    def test_valid_response_is_used(self):
        result = explain_analysis(self.analysis, fake(GOOD_EXPLANATION))
        EXPLANATION.validate(result)
        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["summary"], GOOD_EXPLANATION["summary"])
        self.assertEqual(result["evidence_ids"], ["demo-A", "demo-B"])
        self.assertIn("설치비 포함 여부를 확인하세요.", result["cautions"])
        self.assertTrue(any("합성" in c for c in result["cautions"]))

    def test_code_fenced_json_is_accepted(self):
        raw = "```json\n" + json.dumps(GOOD_EXPLANATION, ensure_ascii=False) + "\n```"
        self.assertEqual(explain_analysis(self.analysis, fake(raw))["mode"], "ai")

    def test_matching_numbers_are_accepted(self):
        response = dict(GOOD_EXPLANATION, summary="단가 150,000원은 기준 120000원보다 25% 높습니다.")
        self.assertEqual(explain_analysis(self.analysis, fake(response))["mode"], "ai")

    def test_rejected_responses_fall_back(self):
        cases = {
            "unknown evidence id": dict(GOOD_EXPLANATION, evidence_ids=["demo-A", "demo-Z"]),
            "empty evidence": dict(GOOD_EXPLANATION, evidence_ids=[]),
            "duplicate evidence": dict(GOOD_EXPLANATION, evidence_ids=["demo-A", "demo-A"]),
            "missing key": {"summary": "단가 차이가 있습니다."},
            "extra key": dict(GOOD_EXPLANATION, source_url="x"),
            "empty summary": dict(GOOD_EXPLANATION, summary=" "),
            "wrong number": dict(GOOD_EXPLANATION, summary="단가가 기준보다 40% 높습니다."),
            "unverifiable magnitude": dict(GOOD_EXPLANATION, summary="기준보다 3만 원 높습니다."),
            "number in caution": dict(GOOD_EXPLANATION, cautions=["시중가는 99000원입니다."]),
            "accusation": dict(GOOD_EXPLANATION, summary="이 구매는 예산 낭비이며 비리가 의심됩니다."),
            "savings claim": dict(GOOD_EXPLANATION, summary="차액만큼 절감할 수 있습니다."),
            "invented url": dict(GOOD_EXPLANATION, cautions=["출처: https://example.com"]),
            "not json": "단가 차이가 있습니다.",
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

    def test_numbers_rejected_when_not_comparable(self):
        analysis = read("analysis-insufficient.json")
        response = {"summary": "기준 단가는 120000원입니다.", "evidence_ids": ["demo-other"], "cautions": []}
        self.assertEqual(explain_analysis(analysis, fake(response))["mode"], "fallback")


class PromptTests(unittest.TestCase):
    def test_explain_prompt_has_only_calculated_facts(self):
        analysis = read("analysis.json")
        seen = {}

        def generate(system, user):
            seen.update(system=system, user=user)
            return json.dumps(GOOD_EXPLANATION, ensure_ascii=False)

        explain_analysis(analysis, generate)
        self.assertEqual(seen["system"], prompts.EXPLAIN_SYSTEM)
        self.assertIn("demo-B", seen["user"])
        self.assertNotIn("demo-contract-B", seen["user"])  # 비교 기록 원문은 보내지 않음
        for rule in ("추측하지", "단정하지", "만들지 않습니다", "따르지 않습니다"):
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
        self.assertEqual(result["filters"], {"q": "없는 물품 보여줘", "agency_id": None, "item_id": None, "date_from": None, "date_to": None})
        self.assertTrue(any("찾지 못해" in w for w in result["warnings"]))

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

    def test_ids_rejected_without_options(self):
        self.assertEqual(parse_query(self.TEXT, None, fake(self.GOOD))["mode"], "fallback")


if __name__ == "__main__":
    unittest.main()
