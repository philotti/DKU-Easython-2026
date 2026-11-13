# 검색·분석·설명 API v1

담당 E(서버·조회), B(계산), C(AI), D(화면). 내부 서버 계약이며 아직 서버는 없습니다. 응답 필드와 타입은 같은 폴더의 JSON Schema가 정본입니다.

## HTTP 경로

| 요청 | 입력 | 응답 스키마 |
|---|---|---|
| GET /api/options | 없음 | options.schema.json |
| GET /api/purchases | 아래 쿼리 | list.schema.json |
| GET /api/purchases/{record_id} | comparison_type=agency 또는 market | analysis.schema.json |
| POST /api/query | JSON `{"text":"예시기관 A 물품을 보여줘"}` | query.schema.json |
| POST /api/purchases/{record_id}/explanation | JSON `{"comparison_type":"agency"}` | explanation.schema.json |

추가 요청 필드는 거절합니다. query의 text는 공백 제거 후 1~500자입니다. comparison_type 기본은 agency. 설명 요청은 선택 유형을 반드시 명시합니다. 성공 200, 요청 오류 400, ID 없음 404, 내부 오류 500이며 오류 본문은 error.schema.json입니다.

## 목록 쿼리

q(선택, 1~200자): 품목명·모델·기관명에 대한 대소문자 무시 부분 문자열 검색. 공백만이면 조건 없음.
agency_id, item_id(선택): 내부 ID 정확 일치.
date_from, date_to(선택): YYYY-MM-DD, 구매일 포함 범위. 역전·잘못된 날짜는 400. 날짜 조건이 있으면 날짜 null 레코드 제외.
comparison_type: agency/market, 기본 agency.
status: comparable/insufficient_data/conditions_unknown/unavailable, 생략하면 전체.
sort: purchased_desc(기본)/difference_pct_desc. 차이율 정렬에는 item_id 필수이며 없으면 400. null은 뒤로, 동률은 record_id 오름차순.
page: 1 이상의 정수, 기본 1. page_size: 1~100 정수, 기본 20. 범위 밖은 400.

필터·정렬 후 페이지를 적용합니다. total은 페이지 전 일치 개수입니다. 없는 페이지는 빈 items. 검색·기관 필터로 분석 비교군을 좁히지 않습니다. 각 대상의 비교군은 전체 데이터와 고정 정책으로 계산합니다. 데이터 버전 안에서 같은 대상·유형은 목록과 상세가 동일해야 합니다.

## 분석 응답

analysis.schema.json의 target은 원본 정규화 구매입니다. comparison_records는 agency일 때 구매 배열, market일 때 시중가 배열입니다. 숫자는 십진 문자열 또는 null, comparison_count는 배열 길이, agency_count는 다른 기관의 고유 수이며 market에서는 null입니다.

evidence_ids는 대상 ID를 먼저, 선택된 비교 기록 ID를 뒤에 나열합니다. 중복 금지. policy_id는 적용한 정책, method_version은 unit-price-v1, dataset_version은 로딩된 데이터 버전입니다. synthetic은 데이터의 실제/합성 구분이며 서버는 혼합 파일을 거절합니다. 상태와 계산은 [비교 규칙](comparison-policy.md)을 따릅니다.

## AI 함수와 응답

- `parse_query(text)` → query.schema.json. filters의 모든 키를 반환하고 모르는 조건은 null. 없는 기관·물품을 지어내지 않고 warnings로 전달. 자동 추출 결과는 화면에 표시·수정 가능.
- `explain_analysis(analysis)` → explanation.schema.json. mode는 ai/fallback. dataset_version·record_id·comparison_type은 입력과 일치해야 함.
- `compare_purchase(record_id, purchases, market_prices, comparison_type)` → analysis.schema.json. E가 정책·버전을 설정한 분석 모듈 사용.

근거 ID는 분석 결과의 부분집합만 허용합니다. 없는 숫자·원인·URL을 생성하지 않습니다. 검증 실패·timeout·할당량 오류에는 fallback 설명으로 200을 반환합니다. 수치와 출처는 AI 설명과 독립적으로 표시합니다. 실제 자료의 출처 URL은 target/comparison_records에서 가져옵니다.

## 화면 표시와 오류

comparable=비교 가능, insufficient_data=비교 자료 부족, conditions_unknown=조건 확인 필요, unavailable=분석 불가. null은 0이 아닙니다. reasons와 limitations를 상세에서 보여줍니다. AI mode=fallback이면 “기본 안내”를 표시합니다. 오류 메시지에는 키·인증 URL·내부 경로를 넣지 않습니다.
