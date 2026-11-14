# 실제 시연 구매 자료 조회 API

`data/demo/purchases.json`의 실제 구매 기록 18건을 읽어 검색·조회합니다. 연간 자료 전체는 아직 API에 연결하지 않았습니다. **B의 비교 함수와 실제 정책은 미연결**이므로 모든 분석 응답은 `unavailable`, 가격 차이·기준은 `null`입니다. 구매 단가는 확인된 원본 자료이며 차액이나 부패 판단이 아닙니다.

## 실행

macOS/Linux, 저장소 루트에서:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-server.txt -r requirements-dev.txt
.venv/bin/python -m uvicorn budget_transparency.api.server:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Windows PowerShell에서는 `.venv/bin/python`을 `.venv\Scripts\python.exe`로 바꾸고 `python3 -m venv .venv` 대신 `py -3 -m venv .venv`를 사용합니다. 종료는 서버 터미널에서 Ctrl+C입니다. 8000번이 이미 사용 중이면 이전 서버를 종료하거나 `--port 8001`을 쓰세요. API 주소: `http://127.0.0.1:8000/docs`.

## 현재 구현된 요청

- `GET /api/options`: 현재 18건에 있는 기관·물품 ID 목록.
- `GET /api/purchases`: 구매 목록. `q`, `agency_id`, `item_id`, `date_from`, `date_to`, `status`, `comparison_type`, `sort`, `page`, `page_size` 사용 가능.
- `GET /api/purchases/{record_id}`: 상세. record_id에 `/`가 포함되므로 클라이언트에서 ID를 URL 인코딩합니다. 목록 응답의 해당 항목과 동일합니다.

예: `http://127.0.0.1:8000/api/purchases?agency_id=6410000&q=Windows`는 경기도 구매 중 Windows가 품목명·모델·기관명에 포함된 건만 반환합니다. q는 대소문자를 구분하지 않는 부분 문자열입니다. 비교 대상 계산에 검색 조건을 재사용하지 않습니다. 오류는 계약의 400/404 형식입니다.

`comparison_type=market`도 현재는 비교 불가를 반환합니다. 비교 결과가 없으므로 `difference_pct_desc`는 `item_id`가 있을 때만 허용하고 모두 ID 순입니다. `status=unavailable` 외 상태로 필터하면 결과가 없습니다.

## 계약상의 임시 표시

분석 응답 v1은 정책 ID·기간을 필수로 요구합니다. 실제 정책이 없으므로 `policy_id: not-configured`는 **실제 정책이 적용되지 않았다는 예약값**입니다. `comparison_period`에는 18건의 원본 자료 수집 범위인 `2025-11-14`~`2026-11-13`을 넣습니다. 이것은 실제 비교 기간이 아니며 `limitations`에도 명시합니다. `method_version: unit-price-v1`은 응답 계약 값이지 계산 실행 증거가 아닙니다. `dataset_version`은 사용한 JSON 파일의 SHA-256입니다. B 함수와 정책을 연결할 때 이 임시 표현을 교체합니다.

실제 기록의 `source_url`이 null인 경우 원본 링크를 만들지 않습니다. `source_id`, `source_record_id`와 [출처 문서](../../../data/sources/purchases.md)로 추적합니다.

## 테스트

```bash
.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v
```
