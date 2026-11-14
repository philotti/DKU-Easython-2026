# B 입력 확인 및 계산 검증 기록

## 2026-11-14 · 작업 순서 2: 비교 함수 구현·검증

- 브랜치: `B/analysis/price-comparison`, 기준 로컬 커밋 `17bd384`, 아래 구현·문서는 커밋 전이다.
- GitHub 검토: main의 재귀 파일 목록을 조회했고, tree SHA `000017bb59c855bc6e7b8bd5ea987a9c57d595db`의 비어 있지 않은 파일을 임시 폴더에 받았다. 기존 로컬 텍스트와 대조했으며, 새 C 모듈·테스트·검증 기록과 공유 JSON 2개를 추가 확인했다. 원격 변경을 현재 브랜치에 병합하지 않았다.
- 구현: `src/budget_transparency/analysis/compare.py`. 네 인자 `compare_purchase`와 초기화 함수 `configure_analysis`, 데이터셋별 `ComparisonEngine`을 제공한다. 기관·시중가 중앙값, 제외 이유, 상태·근거·표본 수·버전 정보를 반환한다. 파일 로딩·서버·Gemini 호출은 없다.
- 정책은 이미 읽은 딕셔너리로 주입한다. 이 초기화 API는 B가 제공하는 인터페이스이며 E의 서버에 반영되거나 E의 확인 답변을 받은 상태는 아니다. [연결 방법과 예외](../../src/budget_transparency/analysis/README.md)를 함께 전달할 수 있다.

### 실행한 명령과 결과

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests/unit -p test_compare.py -v
.venv/Scripts/python.exe -m unittest discover -s tests/unit -p test_contract_validation.py -v
.venv/Scripts/python.exe scripts/check_contracts.py
.venv/Scripts/python.exe scripts/check_data.py
$remote = Join-Path $env:TEMP 'easython-b-main-000017bb59c855bc6e7b8bd5ea987a9c57d595db'
.venv/Scripts/python.exe scripts/check_data.py --file "$remote/data/shared/provinces-20251114-20261113/purchases.json" --schema purchases
.venv/Scripts/python.exe -m unittest discover -s "$remote/tests/unit" -p test_ai_validation.py -v
python3 scripts/check_docs.py
git diff --check
```

| 검사 | 실제 결과 |
|---|---|
| B 함수 테스트 | 27개 통과. 정상 기관·시중가, 홀수·짝수 중앙값, 음수·반올림·긴 소수, 제외 조건, 상태 우선순위, 최소 건수·기관 수, 기간 경계·한국 날짜, 판매처 최신 기록·동률, 입력 불변성, 설정 오류, 실제 unknown 상태 처리 포함 |
| B 기관 비교 | demo-A → 기준 `120000`, 차액 `30000`, 차이율 `25.00`, 비교 3건·3기관. 분석 스키마·기존 수치/참조 검사 통과 |
| B 시중가 비교 | demo-A → 기준 `110000`, 차액 `40000`, 차이율 `36.36`, 판매처 1곳, 적은 표본 한계 표시. 분석 스키마·기존 수치/참조 검사 통과 |
| 등록된 테스트 전용 정책으로 실제 18행 검사 | agency/market 각각 unavailable, 차이 null. 테스트용 정책이며 실제 분석 정책으로 등록하거나 저장하지 않음 |
| 기존 검증기 회귀 테스트 | 9개 통과 |
| 기존 공통 계약 예제 | 15개 통과 |
| 로컬 제출 데이터 | 구매·시중가 2파일 통과 |
| 최신 GitHub 공유 구매 데이터 | 22,987행의 구매 스키마·중복·출처 조건 검사 통과 |
| 최신 GitHub C 테스트 | 30개 통과. 고정 가짜 응답·기본 안내 검증이며 실제 Gemini 호출 아님 |
| B → 최신 C 결과 전달 | 인라인 Python으로 기관 비교·시중가 비교·시중가 없음·조건 불명·표본 부족 5개 결과를 `explain_analysis`에 전달. 모두 fallback 응답 스키마와 근거 ID·데이터 버전 일치 확인 |

추가 인라인 Python 검사에서 공유 구매와 행별 근거 22,987개씩의 record_id가 각각 고유하며 집합도 일치했다. 공유 구매 상태는 전부 unknown, 세금 조건 null 22,981행, 배송·설치 조건 null 각각 22,987행이다. 이는 원본 API의 사실성이나 원본 대조를 B가 다시 완료했다는 뜻은 아니다.

### 남은 연결 범위와 계약 충돌

- 실제 정책은 여전히 미등록이며 실제 가격 비교 가능으로 표시하지 않는다. 원본·화면 숫자의 사람 대조는 미수행이다.
- 기존 서버는 합성 응답 파일을 반환한다. B 함수의 HTTP 연결, 새로운 B 테스트의 CI 등록은 E에게 전달할 후속 작업이다. 이번에 서버 테스트를 재실행하거나 E의 서버 파일·CI를 수정하지 않았다.
- 미등록 정책은 규칙 문서상 unavailable이어야 하지만 분석 스키마에 없는 policy_id·기간을 표현할 방법이 없다. 현재 구현은 미등록/잘못된 정책에 `AnalysisConfigurationError`를 발생시킨다. E와 계약을 정리하기 전까지 이 경우의 unavailable 응답은 미구현이다. 필드·스키마를 임의 변경하거나 가짜 정책으로 회피하지 않았다.
- 요청 오류는 `ValueError`, 없는 ID는 `PurchaseNotFoundError`다. E는 데이터 로딩 오류·서버 설정 오류와 구분해 HTTP 오류로 연결해야 한다.

## 2026-11-14 · PR #3 반영 후 준비 상태 재확인

- 기준 코드: `17bd384`(PR #3 반영), 현재 브랜치 `B/analysis/price-comparison`. 아래 최초 확인 시점과 구분한다.
- A 자료 수신: 현재 브랜치의 `data/demo/purchases.json` 18행·9기관과 `market-prices.json`의 빈 배열을 직접 검사했다. 더 이상 임시 스냅샷에만 있는 상태가 아니다.
- 실행: `.venv/Scripts/python.exe scripts/check_contracts.py` → 합성 예제 15개 통과. `.venv/Scripts/python.exe scripts/check_data.py` → 로컬 제출 JSON 2개 통과.
- 추가 집계: Python 인라인 코드로 18행 모두 unknown, 세금·배송·설치 조건 각각 18행 null, 실제 정책 파일 없음임을 재확인했다.
- 로컬 구매 파일의 바이트 SHA-256: `3e7450d44fd26a1eb4502b54d92536024d080c3f272371b714fcbbf1f562d460`. 최초 PR 임시 파일 해시와 별도로 기록한다.
- **1번 판정:** 입력 수신·필드 형식·읽는 방법 검토 완료. E의 별도 답변과 실제 상태·비용 조건·정책 합의까지 완료된 것은 아니다.
- **2번 판정:** 합성 예제 기준 함수 구현을 시작할 준비가 됐다. 네 인자 함수, 입력·응답 스키마, Decimal 계산 규칙, 합성 정책과 정답 예제, 검증 의존성이 있다. `compare.py`와 `test_compare.py`는 아직 없으며 함수 실행이나 서버 연결을 확인하지 않았다.
- 남은 경계: E가 설정할 정책·데이터 버전 초기화 방식, 정책 없음 응답의 필수 policy_id·comparison_period 표현, 실제 데이터 정책. 이들을 임의 확정하거나 실제 입력을 comparable로 만들지 않는다.

## 2026-11-14 · 작업 순서 1: 계산할 입력 확인

- 담당: B. 커밋 전 작업 기록이다.
- 기준 코드: `e421c9a`, 작업 브랜치 `B/analysis/price-comparison`.
- 범위: 입력 수신·필드 의미·형식·비교 가능 조건의 사전 검토. 분석 함수 구현, 함수 테스트, 실제 가격 차이 계산, 화면 대조는 수행하지 않았다.
- 판정: **입력 형식 검토 완료, 실제 계산 준비 및 A·E 합의는 미완료**. 공통 합성 예제로 다음 단계의 함수를 구현할 수 있다.

### 확인 전 상태와 받은 자료

기존에는 대화에서 PR을 리뷰했으나 B의 입력 확인 기록과 실행한 로컬 입력 검사 결과가 없었다. 이번에 다음 자료를 직접 확인하고 검사했다.

| 자료 | 확인한 위치·버전 | 수신 상태 |
|---|---|---|
| E의 공통 합성 구매·시중가·정책 | `tests/fixtures/contracts-v1/` | 현재 브랜치에 있음. 구매 6행, 시중가 1행 |
| E의 분석 응답과 서버 | `analysis.json`, `analysis-market.json`, `src/budget_transparency/api/server.py` | 서버는 예제 파일을 반환하며 B 함수를 호출하지 않음 |
| A의 실제 구매·시중가·출처·검수 기록 | [PR #3](https://github.com/philotti/DKU-Easython-2026/pull/3), 조회한 head `7e55a3e294f663ac8b774d509ceea21bbca1b227` | OPEN 상태. 변경 파일을 임시 폴더로 받아 검토. B 브랜치에 병합하거나 실제 자료를 합성 입력에 섞지 않음 |
| 실제 분석 정책 | `data/demo/comparison-policy.json` | 현재 브랜치에 없음. 합성 정책을 실제 정책으로 사용하지 않음 |

A의 시연 구매 파일 SHA-256은 `a6362c582efd7c0a8ce559e6f8e7db9e45f821ae4ab7d07747ce691d016c0075`이며 A의 검수 기록에 적힌 값과 일치했다. 연간 22,987행·API 원본의 전수 대조는 이번 B 검증에서 재수행하지 않았다. 최신 A 검수 문서에는 연간 정제본·행별 근거 ZIP의 공유 경로도 추가되어 있으나 이번 검토에서는 내려받거나 검사하지 않았다.

### 입력을 읽는 방법

내부 이름·타입은 [데이터 계약](../contracts/data-model.md), 판단 규칙은 [비교 규칙](../contracts/comparison-policy.md), 함수·응답 경계는 [API 계약](../contracts/analysis-api.md)을 확인했다. 아래 원본 필드 의미는 A가 PR에 등록한 대응표를 검토한 것이며, B가 외부 API 명세나 원본 응답을 재검증한 것은 아니다.

| 입력 | 읽는 방법과 실제 자료 의미 |
|---|---|
| `unit_price`, `currency`, `price_basis` | 금액 문자열을 Decimal로 읽는다. 실제 18행은 A 대응표상 품목 행의 `prdctUprc`, KRW이며 혼합 계약 총액을 수량으로 나눠 산출하지 않는다. 소수 단가 `172840.5`도 그대로 유지한다. |
| `quantity`, `unit` | 수량 문자열은 Decimal, 단위는 원문 문자열. 기관 비교는 수량도 같아야 한다. `조`와 `대`를 변환하거나 같은 단위로 간주하지 않는다. |
| `item_id`, `model`, `specification` | 문자열 식별자·모델·규격을 모두 확인한다. 품목명만으로 일치시키지 않는다. 숫자처럼 보이는 ID도 문자열로 유지한다. |
| `agency_id`, `agency_name` | 대상 기관 제외와 기관 수 집계는 기관 식별자를 기준으로 한다. 기관명은 표시용이다. 원본의 구·현 기관 코드 대응은 별도 확인이 필요하다. |
| `purchased_at` | YYYY-MM-DD의 유효 날짜로 읽는다. A 자료에서 계약일 또는 납품요구일이며, 지급·납품 완료일로 해석하지 않는다. |
| `record_id`, `source_id`, `source_record_id` | 내부 고유 ID와 등록 출처·원본 행 식별자를 구분한다. 실제 18행은 요구번호/차수/순번으로 추적된다. 원본 URL이 null이어도 가짜 링크를 만들지 않는다. |
| `contract_id`, `revision`, `status` | 실제 납품요구의 contract_id는 모 단가계약번호일 수 있다. 같은 모계약의 서로 다른 요구서를 contract_id만으로 중복 제거하지 않는다. 최종 차수 표시를 active나 지급 완료로 추정하지 않는다. |
| 세금·배송·설치 포함 값 | true/false는 확인된 조건, null은 미확인이다. null끼리 같다는 이유로 비교군에 넣지 않는다. |
| `synthetic` | 합성 true와 실제 false는 별도 데이터셋으로 사용한다. |
| 시중가 배열 | 독립 판매처 근거이며 구매 기록에서 생성하지 않는다. 빈 배열은 확인된 시중가 없음이다. |

### 실행한 검사와 실제 결과

검증 의존성을 로컬 `.venv`에 설치했다. 아래 명령은 저장소 루트의 PowerShell에서 실행했다. `$snapshot`은 PR 변경 파일을 저장한 임시 폴더이며 이름은 PR 커밋 버전을 뜻하지 않는다.

```powershell
$snapshot = Join-Path $env:TEMP 'easython-b-input-pr3-20333e7'
.venv/Scripts/python.exe scripts/check_contracts.py
.venv/Scripts/python.exe scripts/check_data.py --file "$snapshot/data/demo/purchases.json" --schema purchases
.venv/Scripts/python.exe scripts/check_data.py --file "$snapshot/data/demo/market-prices.json" --schema market-prices
.venv/Scripts/python.exe -m unittest discover -s tests/unit -p test_contract_validation.py -v
python3 scripts/check_docs.py
git diff --check
```

| 검사 | 실제 결과 | 판정 |
|---|---|---|
| 공통 예제의 스키마 및 적용 가능한 수치·참조 규칙 | `Contract v1: 15 fixtures passed schema and applicable semantic checks` | 통과. B 함수가 실행됐다는 뜻은 아님 |
| A 시연 구매 | `OK`, 18행 구매 스키마·고유 ID·실제/합성 구분·출처 조건 검사 | 통과 |
| A 시중가 | `OK`, 빈 배열 `[]`의 시중가 스키마 검사 | 통과 |
| 기존 계약·데이터 검증기 회귀 테스트 | 9개 테스트 `OK` | 통과. B 계산 함수 테스트는 아님 |
| Markdown 상대 링크 | `Relative Markdown links: OK` | 통과 |
| Git 변경 공백 검사 | 출력 없음, 종료 코드 0 | 통과 |

추가로 PowerShell에서 Python 표준 라이브러리의 `json`, `Decimal`, `date.fromisoformat`, `Counter`, `hashlib`를 사용하는 인라인 코드를 실행했다. 두 구매 배열의 ID 고유성, 양수인 금액·수량 문자열, 날짜 파싱, 제품 식별·단위·기관·금액 근거의 존재를 assertion으로 확인하고 상태·조건·수량 분포와 파일 해시를 집계했다. 파싱·assertion은 모두 통과했다. 결과는 다음과 같다.

| 항목 | 공통 합성 구매 | PR #3 실제 시연 구매 |
|---|---|---|
| 구매 행·기관 수 | 6행·6기관 | 18행·9기관 |
| 구매일 범위 | 2026-11-01 | 2025-11-20~2026-04-29 |
| 상태 | active 6행 | unknown 18행 |
| 세금 조건 null | 1행 | 18행 |
| 배송·설치 조건 null | 각각 0행 | 각각 18행 |
| 시중가 | 합성 1행 | 0행 |

합성 demo-A의 입력은 단가 `150000`, 수량 `1`, 단위 `개`, 기관 `agency-A`, 물품 `demo-item-1`, 모델 `DEMO-100`이다. 합성 정책 `demo-policy-v1`은 기간 2026-11-01~2026-11-13, 최소 3건·3기관, 동일 수량·확인된 동일 조건을 요구한다. 저장된 응답의 정답은 기준 `120000`, 차액 `30000`, 차이율 `25.00`이며, 이번에는 기존 계약 검증기로 이 예제를 검사했다.

### 실제 자료의 계산 가능성

1. 현재 실제 정책이 없고 실제 18행 모두 unknown이다. 규칙상 예상 상태는 unavailable이며 기준 단가·차액·차이율은 모두 null이다. 분석 함수로 실행해 확인한 결과는 아니다.
2. 상태를 근거로 확인하더라도 비용 조건이 모두 null이므로 conditions_unknown 문제가 남는다. 미확인 값을 true/false로 채우지 않는다.
3. Windows 11 Pro(`24445466`)는 9행이지만 수량은 `61/271/1/1/1/13/201/179/320`이다. 동일 수량 1인 세 기관에서 대상 기관을 제외하면 최대 2건·2기관이다. 합성 정책의 최소값 3을 실제 정책으로 확정하지 않으며, 수량이 다른 행을 그대로 합치지 않는다.
4. 시중가는 빈 배열이다. 대상·정책이 유효하고 조건이 확인된 경우에도 market 비교는 insufficient_data가 된다. unknown·정책 없음의 unavailable 우선순위를 유지한다.
5. A의 대응표상 무안청사의 기관 코드는 자료원별 `6460000`과 `6130769`이다. 전체 자료를 사용하기 전 같은 기관 제외·기관 수 집계에 적용할 대응 방식을 A·E와 확인해야 한다.
6. 여러 행이 같은 모 단가계약번호를 공유한다. 내부 ID 18개가 고유하다는 확인을 거래 전체의 중복·취소·변경 검증 완료로 확대하지 않는다.

### A·E에게 확인할 항목과 다음 단계

아래는 전달할 확인 목록이며 메시지를 발송하거나 답변을 받은 기록은 아니다.

| 담당 | 필요한 확인 | 현재 상태 |
|---|---|---|
| A·E | 원본의 유효·취소·변경 정보를 active/cancelled/superseded/unknown으로 매핑하는 근거. 지급 완료와 유효 구매 상태를 구분 | 미확정. B는 unknown을 보존 |
| A | 동일 물품·단위·수량과 비용 조건이 확인된 비교 표본 확보 | 실제 계산 가능한 표본 미확보 |
| A·E | 구·현 기관 코드와 거래·변경본 식별 기준 | 전체 데이터 연결 전 확인 필요 |
| A·B·E | 실제 비교 기간·최소 건수·최소 기관 수와 정책 ID | 실제 정책 미등록 |
| E | 네 인자 함수에 사용할 정책·dataset_version 초기화 인터페이스 | 계약 방향은 확인, 구체적 설정 함수와 E 답변은 없음 |
| E | 정책이 없을 때 unavailable 응답의 policy_id·comparison_period 표현 | 현재 응답 스키마에서 필수값이므로 계약 정리 필요. 임의 정책을 생성하지 않음 |

입력 형식에 관한 질문은 공유 계약과 서버 코드로 확인했다. E에게 별도 확인 답변을 받았다고 기록하지 않는다. 다음 작업은 공통 합성 자료와 등록된 합성 정책으로 `compare_purchase`를 구현하는 것이다. 실제 데이터 계산 가능 판정과 실제 정책 확정은 별도로 남긴다.
