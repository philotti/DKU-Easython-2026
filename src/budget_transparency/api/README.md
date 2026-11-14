# 실제 시연 구매 자료 조회 API

`data/shared/provinces-20251114-20261113/purchases.json`의 실제 연간 구매 기록 22,987건을 읽어 검색·조회합니다. B의 비교 함수는 연결했지만 실제 정책은 아직 등록되지 않았으므로 모든 분석 응답은 `unavailable`, 가격 차이·기준은 `null`입니다. 구매 단가는 확인된 원본 자료이며 차액이나 부패 판단이 아닙니다.

## 실행

macOS/Linux, 저장소 루트에서:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-server.txt -r requirements-dev.txt
.venv/bin/python -m uvicorn budget_transparency.api.server:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Windows PowerShell에서는 `.venv/bin/python`을 `.venv\Scripts\python.exe`로 바꾸고 `python3 -m venv .venv` 대신 `py -3 -m venv .venv`를 사용합니다. 종료는 서버 터미널에서 Ctrl+C입니다. 8000번이 이미 사용 중이면 이전 서버를 종료하거나 `--port 8001`을 쓰세요. API 주소: `http://127.0.0.1:8000/docs`.

## 현재 구현된 요청

- `GET /api/options`: 연간 구매 자료의 기관·물품 ID 목록.
- `GET /api/purchases`: 구매 목록. `q`, `agency_id`, `item_id`, `date_from`, `date_to`, `status`, `comparison_type`, `sort`, `page`, `page_size` 사용 가능.
- `GET /api/purchases/{record_id}`: 상세. record_id에 `/`가 포함되므로 클라이언트에서 ID를 URL 인코딩합니다. 목록 응답의 해당 항목과 동일합니다.

예: `http://127.0.0.1:8000/api/purchases?agency_id=6410000&q=Windows`는 경기도 구매 중 Windows가 품목명·모델·기관명에 포함된 건만 반환합니다. q는 대소문자를 구분하지 않는 부분 문자열입니다. 비교 대상 계산에 검색 조건을 재사용하지 않습니다. 오류는 계약의 400/404 형식입니다.

`comparison_type=market`도 현재는 비교 불가를 반환합니다. 비교 결과가 없으므로 `difference_pct_desc`는 `item_id`가 있을 때만 허용하고 모두 ID 순입니다. `status=unavailable` 외 상태로 필터하면 결과가 없습니다.

## 계약상의 임시 표시

분석 응답 v1은 정책 ID·기간을 필수로 요구합니다. 실제 정책이 없으므로 `policy_id: not-configured`는 **실제 정책이 적용되지 않았다는 예약값**입니다. `comparison_period`에는 연간 원본 자료 수집 범위인 `2025-11-14`~`2026-11-13`을 넣습니다. 이것은 실제 비교 기간이 아니며 `limitations`에도 명시합니다. `method_version: unit-price-v1`은 응답 계약 값이지 계산 실행 증거가 아닙니다. `dataset_version`은 사용한 JSON 파일의 SHA-256입니다. 실제 정책을 등록하면 B 함수의 분석 응답으로 교체됩니다.

실제 기록의 `source_url`이 null인 경우 원본 링크를 만들지 않습니다. `source_id`, `source_record_id`와 [출처 문서](../../../data/sources/purchases.md)로 추적합니다.

## 테스트

```bash
.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v
```

## 상세 설명

`GET /api/explanations/{record_id}?comparison_type=agency`는 서버가 조회한 분석 응답을 C의 설명 함수에 전달합니다. 상세 패널에서만 별도로 요청하므로 설명 호출이 늦거나 실패해도 구매 상세 조회는 유지됩니다. `.env`의 `GEMINI_API_KEY`와 `GEMINI_MODEL`이 모두 있으면 Gemini를 호출하고, 없거나 호출·응답 검증에 실패하면 `mode: fallback`으로 기본 안내를 반환합니다. `mode: ai`는 모델이 고정된 확인 사항의 ID를 선택했다는 뜻이며 자유 문장이나 가격을 생성하지 않습니다. 키 설정 후 서버를 재시작하세요. 실제 모델 호출은 아직 검증하지 않았습니다.

## 비교 함수 연결

실제 비교 정책 `data/demo/comparison-policy.json`이 등록되면 구매 전체와 `data/shared/provinces-20251114-20261113/market-prices.json`을 B 비교 함수에 전달합니다. 정책은 [비교 규칙](../../../docs/contracts/comparison-policy.md)에 따라 A·B·E가 정해야 하며 합성 예제 정책을 실제 분석에 사용하지 않습니다. 정책이 없으면 기존 분석 불가 응답을 반환하고, 잘못된 정책이나 시중가 데이터는 서버 오류로 처리합니다. 정책 적용 시 데이터 버전에는 구매 데이터, 시중가와 정책이 반영됩니다. 현재 실제 구매 기록은 상태·비용 조건이 미확인이라 정책을 등록해도 비교 가능한 수치가 나온다고 보장할 수 없습니다.

## 조건 미확인 참고 비교

`GET /api/preliminary/{record_id}?comparison_type=agency|market`는 엄격한 비교 v1과 별도로 실제 데이터의 참고 가격 차이를 계산합니다. 대상과 후보는 물품 ID·모델·규격·단위·통화가 모두 있고 같아야 하며 가격이 양수여야 합니다. 기관 간은 다른 기관 구매 기록의 중앙값을, 시중가는 연결표에서 verified인 기록과 연결된 판매처별 최신 가격의 중앙값을 사용합니다. 현재 수집 범위의 자료만 쓰고 별도 표본 최소값은 두지 않습니다. 중복되지 않은 판매처만 사용합니다. 상태 unknown을 허용하고 수량·세금·배송·설치 등 조건이 서로 다르거나 확인되지 않을 수 있음을 명시합니다. 이 계산은 이상·부패 판정이나 엄격한 비교 가능 판정이 아닙니다. 시중가는 구매 당시 가격이 아닌 조사일의 가격입니다. 상세 화면에서 참고 수치와 원본 근거를 확인할 수 있으며 기존 AI 설명에는 이 참고 수치가 전달되지 않습니다.

목록 카드는 `GET /api/preliminary?comparison_type=agency&record_id=...`에 ID를 반복해 한 번에 최대 100건의 참고 수치를 요청합니다. 응답에는 상세 근거 원문을 포함하지 않으며 상세 보기에서 따로 조회합니다. 화면의 상태 필터와 차이율 정렬은 참고 계산이 아닌 엄격한 비교 v1을 기준으로 합니다.
