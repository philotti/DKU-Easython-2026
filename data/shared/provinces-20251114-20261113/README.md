# 9개 도 본청 연간 구매 목록과 시중가

2025-11-14~2026-11-13의 구매 22,987행을 보존했다. [구매 목록](purchases.json)과 [시중가](market-prices.json)는 [팀의 계약 v1](../../../docs/contracts/data-model.md)에 맞는 개별 레코드 배열이다. 구매일의 시중가는 확인하지 못했다. 판매가 확인일은 2026-11-14다.

## 개별 구매로 조회하기

1. 구매의 `record_id`로 [구매별 연결표](purchase-list.json)를 찾는다. `market_price_ids`가 null이면 확인된 시중가가 없다. 배열이면 각 ID의 시중가 레코드를 각각 읽는다. 판매가는 205건이고 253개 구매행에 연결된다.
2. 같은 `record_id`로 [원본 페이지와 행 위치](purchase-sources.json), [추가 확인한 모델 근거](model-evidence.json)를 찾는다. 원래 모델이 비어 있던 401행에 나라장터 품목 상세(156행) 또는 원본 규격의 모델 코드와 판매 상세(245행)를 대조해 모델을 채웠다. 나머지 구매 필드는 보관한 정제본과 동일하다. 22,468행은 모델이 null이고, 단위 175행과 식별번호 11행도 null이다.
3. 연결표의 `identity_id`로 [검색 결과](item-search.json)를 찾는다. `group_id`가 있는 경우 [기존 881개 묶음의 구매·판매가 ID](group-members.json)에서 실제 구성원을 확인한다. 같은 판매가가 여러 구매에 연결될 수 있으므로 판매가 ID로 표본을 식별한다.
4. 판매가 ID로 [판매처 증빙](price-evidence.json)과 [가격 조건](market-conditions.json)을 찾는다. 세금·배송·설치는 true/false/null이다. 묶음·옵션·할인은 확인 가능한 문구와 판매처 필드를 남겼고 미확인은 null이다. 문구에 ‘미확인’이 있으면 그 조건을 확정할 수 없다.

## 판매가를 찾지 못한 이유

| 판정 | 품목·규격 | 구매행 |
|---|---:|---:|
| 판매처에서 동일 상품·단위 가격 확인 | 126 | 253 |
| 에누리 검색 결과 0건, 확인 판매가 없음 | 6,664 | 9,959 |
| 검색 결과 있음, 첫 페이지에 모델 문자열 일치 미확인 | 4,744 | 11,330 |
| 첫 페이지에 모델 문자열 일치, 판매가 채택 근거 부족 | 775 | 1,445 |

조사 단위는 식별번호·품명·규격·단위·통화 조합 12,309개다. 고유 검색어 11,561개가 모두 정상 응답했다. 에누리에서 첫 페이지 최대 40개를 읽었고, 검색 결과가 0건인 전체 6,669개 중 5개는 다른 판매처에서 가격을 확인했다. 문자열 일치는 검색 제목 기준이다. 판매 단위·재고·옵션·본품 여부까지 보장하지 않는다.

## 원본 상태와 집계

- `pps-15129471-item` 22,870행은 원본 `fnlCntrctDlvrReqChgOrdYn=Y`인 최종 차수를 선택했다. 최종 차수 표지만으로 취소·유효를 확정할 수 없어 `status=unknown`이다.
- `pps-15129427-goods-detail` 117행은 계약 차수와 삭제 이력을 대조한 물품 상세다. 이행·지급 및 최종 유효 상태는 확인되지 않아 `unknown`이다. [구매 API 필드 대응과 이용 조건](../../sources/purchases.md) · [보관 원본 대조 기록](raw-audit.json)
- 구매마다 원본 단가 `prdctUprc` 또는 `qtyUprcAmt`와 수량을 십진 문자열로 보존했다. VAT는 6행만 포함 확인, 22,981행 미상이다. 배송·설치 포함 여부는 구매 전 행 null이다. 팀 비교 규칙 v1에서 유효 상태가 필요한 가격차 계산은 전 행 unavailable이다.
- 시장가는 판매처별 관측이다. 평균·중앙값·최저가를 산출하지 않았다. 같은 판매 페이지·규격·단위의 재확인에서 최신 기록을 대표로 남긴 4건의 [이전 개별 관측](prior-market-observations.json)과 [최신 ID 대응 및 근거](prior-market-evidence.json)도 보존했다. 이전 관측은 별도 판매처 표본으로 중복 집계하지 않는다.

## 가격 출처와 필드 대응

| 원본 서비스·필드 | 저장 필드와 처리 |
|---|---|
| 에누리 검색어, 응답 listCount.total, items[].name, currentPage | item-search의 search_query, search_hits, model_token_hits_on_page, first_page_rows_checked. 검색 결과는 후보 발견에 사용한다. |
| 소비자원 월별 공개자료의 상품명·제조사·판매업소·조사일·판매가격 | 상품명·제조사는 제품 대조, 판매업소·판매가격은 seller_name·price 후보로 쓴다. 조사일과 자료를 확인한 시각(checked_at)은 별개다. 12개 공개본에서 조달 물품과 같은 제품·판매 단위로 확인된 건이 없어 시장가에 채택한 행은 0건이다. [공식 자료](https://www.data.go.kr/data/15083256/fileData.do) |
| 조달청 가격정보현황서비스의 prceNticeNo, prdctIdntNo, krnPrdctNm, prce, unit, nticeDt, vatYnNm, dlvryCndtnNm | 시설공통자재 공시번호·물품번호·품명·참고가격·단위·공시일·부가세·인도조건. 시설 원가 참고가격으로 분류하며 시장가 또는 구매 비용 필드에 전사하지 않는다. [공식 자료](https://www.data.go.kr/data/15129415/openapi.do) |
| 판매처별 상품 상세 표시가 또는 Offer.price, SKU·모델·상품명·선택 단위, 판매자, 요청 URL·조회 시각 | price, model/specification/unit, seller_name, source_url, checked_at. item_id는 대조한 조달 식별번호다. source_id와 market_price_id가 자료원·관측을 식별한다. 페이지에 표시된 조건은 availability_note 및 판매가 ID별 증빙에서 확인한다. |

판매 페이지의 가격·조건은 확인 시점의 관측이며 저작물·상품 사진의 재배포 권한을 뜻하지 않는다. raw-audit의 구매 파일 해시는 모델 보강 전 원본 대조 입력에 해당한다.
