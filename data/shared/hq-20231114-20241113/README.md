# 2023–24년 12개 본청 물품 구매 자료

2023-11-14부터 2024-11-13까지 나라장터에 등록된 서울·부산·대전 본청의 구매 품목 5,782행과 9개 도 본청의 21,416행을 담았다. 개별 구매 27,198행 중 납품요구는 23,300행, 총액계약은 3,898행이다. 기간 기준은 계약일 또는 납품요구일이며 자료 수집일은 2026-11-14다.

## 팀에서 읽는 순서

| 필요한 자료 | 파일과 연결 방법 |
|---|---|
| 기관별 구매 내역 | [purchases.json](purchases.json)에서 기관·구매일·품목으로 검색한다. 한 행은 구매 품목 한 건이다. 수량과 원화 단가는 원본의 십진 값을 문자열로 보존했다. |
| 다른 본청도 산 동일 품목 | [same-items.json](same-items.json)의 1,025개 그룹에 구매 8,359행이 들어 있다. `provinces[].purchases[].record_id`로 구매 원행을 찾는다. `same_quantity`에 여러 본청의 동일 수량 구매가 있는 그룹은 488개다. |
| 구매 한 건에 연결된 자료 | [purchase-list.json](purchase-list.json)을 구매와 같은 `record_id`로 찾는다. `group_id`, `market_price_ids`, `historical_announcement_ids`, `reference_20261114_market_price_ids`는 각각 동일 품목, 구매일 시중가, 제조사 발표가, 2026년 참고 판매가로 연결한다. 확인된 연결이 없으면 `null`이다. |
| 구매 당시 시중가 | [market-prices.json](market-prices.json)은 빈 배열이다. 구매일에 동일 제품·판매 단위로 확인된 판매가가 0건이다. |
| 구매 원본 | [purchase-sources.json](purchase-sources.json)에서 `record_id`를 찾아 `evidence_file`을 이 폴더 기준으로 연다. `source_pages[raw_page].rows[row_index]`가 해당 원문 행이고 행 번호는 0부터 센다. [시 본청 원문 발췌](evidence/cities/shopping-source-snapshot.json) · [도 본청 원문 발췌](evidence/provinces/shopping-source-snapshot.json) |
| 모델 및 계약 확인 | [물품목록 근거](evidence/models.json)의 `record_ids`로 모델을 확인한 10,383행을 추적한다. 구매 출처에 `central_report_source_ids`가 있으면 [계약보고서 발췌](evidence/contract-report-lines.json)의 `source_record_id`에서 대조한 194행을 찾을 수 있다. |

## 가격 근거의 시점

- [제조사 발표 근거](evidence/historical-price-references.json)의 `references[].reference_id`로 당시 발표된 두 모델의 공표가를 조회할 수 있다. 구매 3행과 제품이 일치하고 해당 구매일의 판매 조건은 미확인이다.
- [2026-11-14 참고 판매가](reference-20261114/market-prices.json)에는 40개 물품의 판매처별 관측 62건이 있다. 구매 140행과 연결되며, [판매처 근거](reference-20261114/evidence.json)에서 같은 `market_price_id`로 판매 페이지·옵션·포장·가격을 확인할 수 있다. 화면에서 이 가격을 표시할 때는 관측일을 함께 표시한다.

## 원본 필드와 비교 조건

| 원본 | 구매 JSON에서의 의미 |
|---|---|
| `dminsttCd`, `dminsttNm` | `agency_id`, `agency_name`은 원본 기관 코드와 이름이다. 동일 본청을 묶을 때는 강원 6420000·6530000, 전북 6450000·6540000을 각각 한 곳으로 센다. 전남은 6130769로 반환됐고 그룹의 대표 코드는 6460000이다. |
| `cntrctDlvrReqNo`, `cntrctDlvrReqChgOrd`, `prdctSno` | 계약·납품요구 번호, 차수, 품목 순번이 `source_record_id`를 구성한다. 내부 `record_id`에는 원본 기관 코드도 들어간다. |
| `cntrctDlvrReqDate`, `cntrctDlvrDivNm` | `purchased_at`에 총액계약일 또는 납품요구일을 기록했다. |
| `prdctIdntNo`, `dtilPrdctClsfcNoNm`, `prdctIdntNoNm` | 물품식별번호, 품목명, 원문 규격이다. 세부품명이 비면 상위 품명을 사용했다. 그룹은 식별번호·품목명·규격·단위·통화가 모두 일치하고 두 곳 이상의 본청이 구매한 품목으로 구성했다. |
| `prdctQty`, `prdctUnit`, `prdctUprc`, `prdctAmt` | `quantity`, `unit`, `unit_price`는 수량·단위·개별 단가다. 품목금액 `prdctAmt`는 출처 파일에서 별도로 확인할 수 있다. |

원본 395페이지의 최종 차수 품목 29,540행 중 공사·용역 2,342행을 제외하고 물품 구매 27,198행을 원본과 대조했다. 최종 차수만으로는 취소·이행 여부를 확인할 수 없어 구매 상태는 모두 `unknown`이다. 세금·배송·설치 포함 여부도 `null`이다. 비교 규칙 v1에서 가격 차이 계산은 `unavailable`이다. [구매·시중가 계약 v1](../../../docs/contracts/data-model.md) · [비교 규칙](../../../docs/contracts/comparison-policy.md)

조달청 쇼핑몰 품목정보의 출처 ID는 `pps-15129471-item`이다. 포털 이용허락범위는 ‘제한 없음’이며 공개 응답에서 구매 검증에 필요한 필드를 발췌했다. 중앙조달 보고서의 계약·차수·품목·수량·단가·금액이 일치한 경우에만 교차 근거로 연결했다. [조달청 쇼핑몰 품목정보](https://www.data.go.kr/data/15129471/openapi.do) · [중앙조달 계약보고서](https://data.g2b.go.kr/link/AISC001_01/?reptNm=UI-ADOXFA-191R) · [팀 출처 등록부](../../sources/purchases.md)
