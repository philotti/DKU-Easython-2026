# 구매·시중가 데이터 형식 v1

담당 A, 검토 B·E. 공공 API 필드명이 아니라 우리가 JSON에 저장할 내부 이름입니다. 아직 실제 자료에 적용해 검증하지 않았습니다.

## 공통 규칙

구매 파일과 시중가 파일은 각각 레코드의 배열로 저장합니다. 금액·수량은 JSON에서 정밀도를 보존하는 십진 문자열을 사용합니다. 예: `"150000"`, `"1.5"`. B는 Decimal 등 정밀 소수로 계산하고 D는 E가 제공한 표시 함수를 사용합니다. 필드는 생략하지 않고 결측은 null로 표현합니다. 추가 필드는 허용하지 않습니다.

날짜는 YYYY-MM-DD, 수집 시각은 시간대가 있는 ISO 8601 문자열로 통일합니다. 결측은 null, 조건 확인 값은 true/false/null입니다. 실제·합성 자료는 별도 파일로 분리하고 `synthetic`으로도 표시합니다.

## 구매 레코드 — purchases.json

| 필드 | 타입·의미 | 확인 사항 |
|---|---|---|
| record_id | 문자열, 내부 고유 ID | 중복 금지 |
| synthetic | 불리언 | 예제 true, 확인한 실제 자료 false |
| source_id / source_record_id | 문자열 또는 null, 출처·원본 ID | 실제 자료는 추적 가능한 근거 필요 |
| item_id / item_name | 식별자 / 표시 이름 | 이름만 같다고 동일 물품 아님 |
| model / specification | 문자열 또는 null | 모델·규격 |
| agency_id / agency_name | 문자열 | 기관 식별·표시 |
| purchased_at | 날짜 또는 null | 원본 날짜 의미 기록 |
| quantity / unit | 십진 문자열 또는 null / 단위 | 0·음수·단위 불명은 비교 제외 |
| unit_price / currency | 십진 문자열 또는 null / 통화 | 총액과 혼동 금지 |
| price_basis | 문자열 | 원본 단가 필드 또는 검증된 산출 근거 |
| tax_included / delivery_included / installation_included | 불리언 또는 null | 모르면 null |
| contract_id / revision / status | 문자열 또는 null | 변경·취소·중복 구분, 원본 상태 의미 기록 |
| source_url / retrieved_at | URL 또는 null / 수집 시각 | 키 포함 URL 금지 |

식별자나 단가가 없다고 임의 값을 채우지 않습니다. 저장은 가능해도 비교할 수 없는 기록은 B가 이유와 함께 제외합니다. 원본 상태 문자열은 A·E가 정한 매핑으로 해석합니다.

## 시중가 레코드 — market-prices.json

| 필드 | 의미 |
|---|---|
| market_price_id / synthetic | 시중가 근거 ID / 합성 여부 |
| item_id / model / specification | 동일 제품 확인 정보 |
| seller_name / checked_at | 판매처 / 가격 확인 시각 |
| price / currency / unit | 십진 문자열 가격 / 통화 / 수량 단위 |
| tax_included / delivery_included / installation_included | 포함 조건, 모르면 null |
| source_id / source_url | 출처 등록 ID / 확인한 판매 페이지 |
| availability_note | 재고·옵션·구매 조건 등 확인 내용 |

시중가 자료가 없으면 파일에는 `[]`를 넣습니다. 다른 기관 가격을 시중가로 복사하지 않습니다. 가격 채택 기준은 실제 자료를 본 A·B·E가 결정합니다.

## 최소 합성 예제의 내용

E는 같은 규격의 가상 제품을 예시기관 A/B/C/D가 각각 150000/100000/120000/140000원에 구매한 예제를 만듭니다. 숫자는 문자열로 저장하고 `synthetic: true`, 원본 URL은 null로 둡니다. 조건이 확인된 예제로 구성해야 비교 가능 상태를 시험할 수 있습니다. 별도로 조건 불명·다른 규격·표본 부족 사례를 추가합니다. 전체 합성 파일은 tests/fixtures/contracts-v1/에 준비되어 있습니다. 실제 데이터가 아닙니다.

## 스키마와 상태

purchases.schema.json과 market-prices.schema.json이 필수 필드·타입의 정본입니다. currency는 v1에서 KRW만 지원합니다. 구매 status는 active/cancelled/superseded/unknown입니다. 원본 상태를 확인하지 못하면 unknown으로 둡니다. 실제 자료는 source_id와 source_record_id 또는 추적 가능한 원본 URL이 필요합니다. 합성 자료는 source URL을 null로 두고 UI에서 예시 표시합니다.
