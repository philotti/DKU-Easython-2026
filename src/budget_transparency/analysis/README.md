# B 가격 비교 모듈

`compare.py`는 이미 읽은 구매·시중가 배열을 받아 분석 계약 v1의 딕셔너리를 반환한다. 파일 로딩, 서버, Gemini 호출은 없다. Python 표준 라이브러리만 사용한다. 입력 배열의 전체 스키마·출처·실제/합성 구분 검사는 E의 로딩 단계에서 수행하며, 함수에서도 ID 중복과 실제/합성 혼합은 거절한다.

## E가 연결하는 방법

E가 읽고 검증한 정책과 데이터 버전을 서버 시작 시 한 번 설정한다. 아래 변수는 모두 E가 이미 로딩한 객체다. 실제 정책은 합성 정책과 별도로 등록해야 한다.

이 import 예제는 `src`가 Python 경로에 있는 서버 환경 기준이다. 현재 서버 실행 명령의 `--app-dir src`가 이 경로를 설정한다.

```python
from budget_transparency.analysis.compare import configure_analysis, compare_purchase

configure_analysis(policy, dataset_version)
analysis = compare_purchase(record_id, purchases, market_prices, "agency")
market_analysis = compare_purchase(record_id, purchases, market_prices, "market")
```

여러 데이터셋·버전을 동시에 다루는 서버는 모듈 설정을 요청마다 바꾸지 않고 독립 엔진을 보관한다.

```python
from budget_transparency.analysis.compare import ComparisonEngine

engine = ComparisonEngine(policy, dataset_version)
analysis = engine.compare_purchase(record_id, purchases, market_prices, "agency")
```

정책은 엔진 생성 시 복사한다. 입력과 반환 근거도 서로 독립이므로 응답을 수정해도 원본 배열은 바뀌지 않는다. 정책은 `policy.schema.json`의 모든 필드와 지원 규칙을 만족해야 한다. 서버에서 검색·기관 필터를 적용하기 전의 전체 구매 배열을 전달한다.

## 계산과 예외

- 기관 비교: 동일 물품·모델·규격·단위·통화·확인된 비용 조건·동일 수량, 정책 기간 안의 다른 기관 구매만 선택한다. 구매일이 구매 정책 기간 밖인 대상도 unavailable이다.
- 시중가 비교: 한국 날짜로 정책 기간을 적용하고 판매처·물품별 최신 확인 기록을 먼저 선택한다. 같은 시각이면 ID 오름차순으로 선택한다. 최신 기록의 조건이 불명확하다고 이전의 유리한 가격으로 바꾸지 않는다.
- 기관은 적격 구매 건별 중앙값, 시중가는 적격 판매처 가격 중앙값을 사용한다. Decimal로 계산하며 차이율만 소수 둘째 자리 ROUND_HALF_UP이다.
- 상태 우선순위는 unavailable → conditions_unknown → insufficient_data → comparable이다. 비교 불가 수치는 null이다. 이유·제외 ID·표본 수·기관 수·선택된 근거를 함께 반환한다.
- 중복 ID는 ValueError다. 동일 출처·원본 행·기관의 동일한 복사본은 하나만 비교에 쓰고 나머지를 제외한다. 서로 내용이 다른 복사본은 임의 선택하지 않고 ValueError다. 모 단가계약번호가 같다는 이유만으로 서로 다른 요구서를 중복 제거하지 않는다. 최신 유효 변경본의 정규화는 A·E 책임이다.
- `PurchaseNotFoundError`: 없는 구매 ID. E가 404로 변환할 수 있다.
- `ValueError`: 지원하지 않는 comparison_type, 중복 ID, 실제/합성 혼합 등. E는 요청 오류와 데이터 로딩 오류를 구분해야 한다.
- `AnalysisConfigurationError`: 정책·버전 미설정 또는 잘못된 정책. 실제 자료가 부족하다는 의미와 구분해야 한다.

## 미등록 정책의 계약 충돌

[비교 규칙](../../../docs/contracts/comparison-policy.md)은 정책 미등록 시 unavailable을 요구하지만 [분석 스키마](../../../docs/contracts/analysis.schema.json)는 policy_id와 비교 기간의 유효값을 반드시 요구한다. 없는 정책의 ID·기간을 만들어 응답하거나 스키마를 독단적으로 바꾸지 않았다. 현재 구현은 **정책 미등록 시 분석 응답 대신 AnalysisConfigurationError를 발생**시킨다. E는 초기화 단계에서 이를 발견할 수 있다. 정책 없음의 unavailable 응답 표현은 E와 계약·스키마·소비자 검토 후 확정할 남은 항목이다. 등록된 정책에서 대상 unknown·취소 등은 계약에 맞는 unavailable 분석 응답을 반환한다.

## 검사

저장소 루트에서 개발 의존성을 설치한 Python으로 실행한다.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests/unit -p test_compare.py -v
```

macOS/Linux에서는 `.venv/bin/python`을 사용한다. 합성 예제 기준 기관 비교는 `30000`·`25.00`, 시중가 비교는 `40000`·`36.36`이다. E의 현재 서버는 여전히 예제 JSON을 반환하므로 이 함수가 HTTP 경로에 연결된 상태는 아니다.
