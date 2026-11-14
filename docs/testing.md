# 기능을 직접 확인하는 방법

> D 화면은 도청 목록·분석 순위·도청별 상세 근거 구조로 변경했습니다. 현재 D 검수는 [웹 검증 기록](evidence/ui-check.md)을 따릅니다. 아래 구매 카드 기반 D 항목은 이전 방향이며 실제 분석값 검증은 데이터 연결 후 진행합니다.

모델 학습·별도 실험은 하지 않습니다. 각 역할은 자신의 기능을 확인하고, 결과는 [검증 기록](evidence/README.md)에 남깁니다. 아래 테스트 파일과 서비스 명령은 구현 예정이며 아직 통과한 것으로 간주하지 않습니다.

## 역할별 확인표

| 담당 | 입력·행동 | 기대 결과 | 기록 |
|---|---|---|---|
| A | 시연 구매 행을 원본과 대조 | 제품·기관·단가·수량·날짜 일치 | data-check.md |
| A | 시중가 자료를 제거 | 빈 배열, 없는 가격 생성 안 함 | data-check.md |
| B | 대상 150000, 비교 100000·120000·140000 | 기준 120000, 차액 30000, 차이율 25 | calculation-check.md |
| B | 같은 기관·다른 규격·중복 기록 추가 | 비교군 제외와 이유 반환 | calculation-check.md |
| B | 비교군 없음·기준 0·조건 null | 계산 불가 상태, 차이 null | calculation-check.md |
| B | 대상 가격이 기준보다 낮음 | 음의 차액·차이율, 절대값으로 바꾸지 않음 | calculation-check.md |
| C | 기관만/품목만/둘 다/날짜/없는 물품 질문 | 해석 가능한 조건만 반환 | ai-check.md |
| C | 없는 근거 ID·잘못된 JSON·불일치 숫자 응답 | 거절 후 기본 설명 | ai-check.md |
| C | 시간 초과·한도 초과 | fallback 응답 | ai-check.md |
| D | 다른 카드 두 개 클릭 | 각각의 상세 정보 표시 | ui-check.md |
| D | 필터·검색·정렬·비교 유형 변경 | 목록·라벨·근거가 함께 변경 | ui-check.md |
| D | Esc·모바일·키보드 사용 | 닫기·스크롤·포커스 정상 | ui-check.md |
| E | 실제 자료 검색 → 카드 → 상세 → 원본 | 수치와 출처 일치 | integration-check.md |
| E | 다른 팀원이 실행 안내를 따름 | 같은 시연 재현 | integration-check.md |

기록 파일은 `docs/evidence/` 아래에 작성합니다. 존재하지 않는 원본·실제 기관을 합성 예제에 붙이지 않습니다.

## 자동 테스트와 사람이 확인할 부분

B는 `tests/unit/test_compare.py`, C는 `tests/unit/test_ai_validation.py`, E는 `tests/integration/test_flow.py`를 만듭니다. E가 테스트 도구를 정한 뒤 실제 실행 명령을 README와 기록에 추가합니다. AI 응답 형식·실패 테스트는 고정된 가짜 응답으로 재현하고, 실제 Gemini 호출 성공 확인은 별도로 기록합니다.

원본 가격의 의미, 상품 규격, 화면의 읽기 쉬움은 자동 테스트만으로 통과 처리하지 않습니다. A·B의 원본 대조와 D의 화면 검수가 필요합니다.

## 실패하면

입력, 기대값, 실제값, 재현 순서, 담당자를 적고 수정 후 같은 사례를 다시 확인합니다. 확인하지 않은 항목은 미확인으로 남깁니다. 실패 사례를 삭제해서 모두 통과한 것처럼 만들지 않습니다.

## 현재 문서에서 가능한 검사

`python3 scripts/check_docs.py`는 상대 링크 검사이고 `git diff --check`는 공백 오류 검사입니다. 웹 기능 테스트 결과와 구별합니다.

## 현재 구현된 검증 도구

계약 예제 검사는 scripts/check_contracts.py, 제출 JSON 검사는 scripts/check_data.py, 검증기 회귀 테스트는 tests/unit/test_contract_validation.py입니다. 서비스 기능 테스트와 별개이며 [CI 안내](ci.md)에 자동 실행 범위를 정리했습니다.
