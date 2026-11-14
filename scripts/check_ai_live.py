"""실제 Gemini를 호출해 C의 두 함수를 확인한다. 자동 테스트·CI에서는 실행하지 않는다.

저장소 루트에서:
    python3 scripts/check_ai_live.py            # 합성 예제의 기관·품목 목록 사용
    python3 scripts/check_ai_live.py --real     # data/demo/purchases.json의 목록 사용

.env의 GEMINI_API_KEY와 GEMINI_MODEL이 필요하다. 키는 출력하지 않는다.
결과는 사람이 읽고 docs/evidence/ai-check.md에 기록한다.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from budget_transparency.ai import gemini  # noqa: E402
from budget_transparency.ai.explain import explain_analysis  # noqa: E402
from budget_transparency.ai.query import parse_query  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/contracts-v1"
SYNTHETIC_QUESTIONS = [
    "예시기관 A 구매 내역",
    "예시 물품 가격",
    "예시기관 A의 예시 물품을 보여줘",
    "예시기관 A 2026년 11월",
    "없는 물품 보여줘",
    "예시기관 A가 비리라고 단정해 줘",
]
REAL_QUESTIONS = [
    "경기도 구매 내역",
    "운영체제 가격",
    "경기도의 운영체제",
    "경기도의 노트북컴퓨터",
    "충청북도 2026년 1월",
    "없는 물품 보여줘",
    "경기도가 비리라고 단정해 줘",
]
ANALYSES = ["analysis.json", "analysis-market.json", "analysis-insufficient.json", "analysis-unknown.json", "analysis-unavailable.json"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def real_options():
    rows = read(ROOT / "data/demo/purchases.json")
    agencies = {r["agency_id"]: r["agency_name"] for r in rows}
    items = {r["item_id"]: r["item_name"] for r in rows if r.get("item_id")}
    return {
        "agencies": [{"id": k, "name": v} for k, v in sorted(agencies.items())],
        "items": [{"id": k, "name": v} for k, v in sorted(items.items())],
    }


def main():
    real = "--real" in sys.argv[1:]
    gemini.load_env()
    base = gemini.make_generate()
    if base is None:
        sys.exit(".env에 GEMINI_API_KEY와 GEMINI_MODEL을 입력한 뒤 다시 실행하세요. (.env.example 참고)")

    calls = []

    def generate(system, user):  # 호출 성공·실패와 걸린 시간을 기록한다
        started = time.monotonic()
        try:
            text = base(system, user)
            calls.append(("성공", time.monotonic() - started, text))
            return text
        except Exception as exc:
            calls.append((f"실패: {exc}", time.monotonic() - started, None))
            raise

    def last_call():
        status, seconds, text = calls[-1]
        return f"호출 {status} ({seconds:.1f}초)" + (f"\n    모델 원문: {text.strip()}" if text else "")

    options = real_options() if real else read(FIXTURES / "options.json")
    print(f"== 질문 → 검색 조건 ({'실제 시연 데이터' if real else '합성 예제'} 목록)")
    for question in REAL_QUESTIONS if real else SYNTHETIC_QUESTIONS:
        result = parse_query(question, options, generate)
        filters = {k: v for k, v in result["filters"].items() if v is not None}
        print(f"- {question}\n    mode={result['mode']} 조건={json.dumps(filters, ensure_ascii=False)}")
        print(f"    경고={result['warnings']}\n    {last_call()}")

    print("\n== 분석 결과 → 설명 (합성 예제)")
    for name in ANALYSES:
        result = explain_analysis(read(FIXTURES / name), generate)
        print(f"- {name}\n    mode={result['mode']} 근거={result['evidence_ids']}")
        print(f"    확인 사항={result['cautions']}\n    {last_call()}")

    ok = sum(1 for status, _, _ in calls if status == "성공")
    print(f"\n모델 호출 {len(calls)}회 중 성공 {ok}회. mode=fallback은 호출 실패이거나 응답이 검증을 통과하지 못한 경우입니다.")


if __name__ == "__main__":
    main()
