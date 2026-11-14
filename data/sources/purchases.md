# 9개 도 본청의 물품 구매 원본

연간 자료의 기준 기간은 2025-11-14~2026-11-13(한국 날짜, 양 끝 포함)이다. 2026-11-14에 수집했다. 수요기관 **본청 코드**를 지정해 모든 품명을 조회했다. 처리한 범위는 나라장터에서 해당 기관코드와 기간으로 공개하는 물품 계약·납품요구다. 도 산하 시군·교육청·사업소의 별도 기관코드와 나라장터 외 지출은 대상 밖이다.

| 자료 | 수집 방법과 재조회 식별자 |
|---|---|
| 조달청 나라장터쇼핑몰 품목정보 서비스 15129471 | `getSpcifyPrdlstPrcureInfoList`의 특정품목조달내역. `inqryDiv=1`, `inqryPrdctDiv=1`, 품명 `prdctClsfcNoNm=%`, 기관코드 `dminsttCd`, 최종차수 `fnlCntrctDlvrReqChgOrdYn=Y`. 13개 달력 구간(첫 달과 마지막 달은 부분월), 페이지당 500행. API가 반환한 기관·날짜·최종 여부와 페이지별 건수를 재검사했다. |
| 같은 서비스의 요구서·계약품목 | 같은 기관·기간을 `getDlvrReqInfoList`로 따로 조회해 쇼핑몰 요구번호와 차수를 대조했다. 개별 요구서는 `getDlvrReqDtlInfoList`에 `inqryDiv=2`와 요구번호를 주면 된다. 개별 행은 요구번호·요구변경차수·물품순번으로 찾는다. 일부 확인한 MAS 품목의 조건은 `getMASCntrctPrdctInfoList` 응답을 사용했다. |
| 조달청 계약정보서비스 15129427 | `getCntrctInfoListThngPPSSrch`에서 계약체결일과 수요기관으로 공개 물품계약을 조회했다. 이 원장이 계약과정 API의 조회 식별자를 제공한다. |
| 조달청 계약과정통합공개서비스 15129459 | `getCntrctProcssIntgOpenThng`에 원본 입찰공고번호 또는 조달요청번호를 입력해 단계 자료를 받았다. 공식 ID가 기재된 발주계획·사전규격·공고·개찰/낙찰·계약을 기록했다. |
| 조달데이터허브 공개 보고서 UI-ADOXAA-038R | ‘나라장터쇼핑몰 납품요구 물품 내역’에서 하위기관 미포함으로 내려받은 파일을 보조 대조에 사용했다. 화면 열 이름은 납품요구일자, 포털의 보고서 기간 설명은 결재일자다. 표시 정밀도·업데이트 시각 차이는 검수 기록에 적었다. |

공공데이터포털에는 위 조달청 자료의 이용허락범위가 ‘제한 없음’으로 표시돼 있다. 제공기관·데이터셋·기준일을 함께 기재했다. 공유 파일은 정해진 구매 필드만 담는다. 응답 원문은 Git 제외 로컬 폴더에 보관하며 연락처·사업자번호·담당자·조달 인증키를 공유용 구매 데이터에 넣지 않았다. 사용자가 제공한 쇼핑몰 명세 1.3과 계약과정 명세 1.0의 필드표를 적용했다. [쇼핑몰·특정품목 조달내역](https://www.data.go.kr/data/15129471/openapi.do) · [계약정보](https://www.data.go.kr/data/15129427/openapi.do) · [계약과정](https://www.data.go.kr/data/15129459/openapi.do) · [쇼핑몰 납품요구 보고서](https://www.data.go.kr/data/15053481/fileData.do)

## 구매 레코드의 필드 대응

아래는 `pps-15129471-item` 행의 대응이다. 계약체결 원장과 납품요구 행은 같은 시간축이나 같은 단위로 집계되지 않으므로 출처 ID와 원본 키를 유지한다. [구매 데이터 v1](../../docs/contracts/data-model.md)

| 원본 열 또는 출처 | 내부 필드 | 처리 |
|---|---|---|
| 기관코드 + 계약납품요구번호 / 변경차수 / 물품순번 | `record_id`, `source_record_id` | 원본 키를 `번호/차수/순번`으로 보존. 내부 ID는 앞에 `pps:기관코드:`를 붙인다. 앞자리 0을 보존한다. |
| 출처 등록 및 HTTP 수집 시각 | `source_id`, `source_url`, `retrieved_at`, `synthetic` | 출처는 `pps-15129471-item`, 수집시각은 응답별 한국 시각, 실제 자료이므로 false. 행별 영구 URL을 확인할 수 없어 null. 아래 공식 보고서와 식별자로 원본을 찾을 수 있다. |
| `prdctIdntNo`, `dtilPrdctClsfcNoNm`, `prdctClsfcNoNm` | `item_id`, `item_name` | 물품식별번호와 세부품명. 후자가 비면 상위 품명을 사용한다. |
| `prdctIdntNoNm` | `specification`, `model` | 원문 규격명을 보존한다. 시연용 사무기기·소프트웨어 등은 제조사 다음의 모델 토큰을 확인한 경우만 추출한다. 규격·모델이 불명확하면 해당 값은 null이다. |
| `dminsttCd`, `dminsttNm` | `agency_id`, `agency_name` | API가 준 본청 코드·명칭. 무안청사는 쇼핑·조달내역 API에서 6460000이며 구매시점이 과거인 행에도 현재 명칭이 표시된다. 계약 원장의 대응은 아래 설명을 따른다. |
| `cntrctDlvrReqDate`, `cntrctDlvrDivNm` | `purchased_at` | 총액계약의 계약일 또는 납품요구일을 YYYY-MM-DD로 기록한다. 지급·검수 시점은 별도 자료가 필요하다. |
| `prdctQty`, `prdctUnit` | `quantity`, `unit` | 품목 행의 수량·원본 단위. 소수점과 실제 0을 보존한다. |
| `prdctUprc` | `unit_price`, `currency`, `price_basis` | 명세가 원화 단가로 정의한다. KRW, 십진 문자열. 계약유형과 원본 열을 함께 남긴다. `prdctAmt`는 품목금액으로 검수용에 보존한다. |
| `uprcCntrctNo` 또는 `cntrctDlvrReqNo` | `contract_id` | 납품요구의 모 단가계약번호는 원문의 `_1` 등의 접미사를 포함해 보존한다. 총액계약은 해당 계약번호를 쓴다. |
| `cntrctDlvrReqChgOrd`, `fnlCntrctDlvrReqChgOrdYn` | `revision`, `status` | 최종 표시 Y인 원본 차수를 저장한다. 최종차수 표지만으로 유효·취소·지급 여부를 확정할 수 없어 `unknown`으로 기록한다. 수량 0인 행도 추적 가능하다. |
| MAS 계약번호·계약차수·식별번호·규격·계약 적용일과 `vatAplDivNm` | `tax_included` | 식별번호 23266511, 모계약 0024C0530_1, 계약차수 02가 당시 MAS 품목 원본과 일치하고 부가가치세 포함이 명시된 행만 true. 나머지 미확인 값은 null이다. |
| `dlvryCndtnNm` | `delivery_included`, `installation_included` | 인도조건 원문은 근거 파일에 남긴다. 가격에 포함된 개별 비용을 별도로 확인하지 못해 두 필드는 null이다. |

[원본 보고서 열기](https://data.g2b.go.kr/link/AISC001_01/?reptNm=UI-ADOXAA-038R)

## 파일을 찾는 법

- `data/processed/provinces-20251114-20261113/purchases.json`에 연간 정제본을 구매 v1 배열로 저장했다. `data/demo/purchases.json`에는 기관별로 출처를 확인한 시연용 2행씩을 담았다. 하나는 9개 본청 모두에서 확인한 Microsoft Windows 11 Pro(24445466), 하나는 모델을 확인한 사무기기다. 전체 연간 자료는 전 품목을 대상으로 한다.
- 같은 정제 폴더의 `purchase-sources.json`에는 행별 출처 페이지·페이지 안의 위치(0부터), 거래유형, 인도조건, 모계약번호와 변경차수, 매칭된 통합계약번호·공고차수가 있다. `excluded-lines.json`에는 각 공사·용역 행의 원본 ID·분류·제외 이유가 있다.
- `contract-process.json`의 `contracts`에서 통합계약번호와 기관을 찾고 `exact_contract_refs`로 `notice_stages`를 연다. 구매 근거와 연결할 때 총액계약번호+변경차수, 기관, 계약일이 일치한 경우만 채택했다. 납품요구에 모계약의 낙찰 결과를 개별 납품요구의 입찰로 붙이지 않는다.
- `data/raw/provinces-20251114-20261113/`의 `shopping-responses.tar.gz` 및 `shopping-manifest.json`에 공식 응답과 원문별 SHA-256·수집시각·검색조건이 있다. `contract-process-raw.tar.gz`에는 계약 API 원본과 매니페스트가 있다. [원본 대조 기록](../../docs/evidence/data-check.md)에 인도 파일의 해시와 범위가 있다.
- 이번에 수집한 조달 자료에는 독립 판매처 소매가가 없어 `data/demo/market-prices.json`은 빈 배열이다.

무안청사 자료에서 조달내역은 6460000, 계약정보 원장은 6130769로 같은 본청을 돌려준다. 두 코드 모두 계약정보 API에서 확인하고 원본 필드를 보존했다. 광주청사·동부청사의 별도 기관코드는 범위 밖이다. [행정안전부 통합 안내](https://www.mois.go.kr/frt/bbs/type010/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000008&nttId=126845)

## 보조 물품계약 상세

쇼핑몰 품목정보와 계약정보 원장의 수요기관·기초계약번호를 먼저 맞췄다. 양쪽에 있는 기초계약 1,973개는 차수를 확인해 중복 추가를 막았다. 계약 원장에서만 찾은 기초계약 162개에 대해 최신 차수의 물품 상세, 바로 다음 차수 유무와 삭제 이력을 조회했다. 채택한 원본은 107개 기초계약의 117품목행이다. 미채택 67행을 포함한 원본 위치·사유는 연간 폴더의 `supplemental-evidence.json`에 있다. [조달청 물품계약 상세](https://www.data.go.kr/data/15129427/openapi.do)

| 보조 원본 | 내부 필드 | 변환 및 의미 |
|---|---|---|
| 실제 응답의 통합계약번호·페이지·행 위치 | `source_id`, `source_record_id`, `record_id` | 출처는 `pps-15129427-goods-detail`. 원본 ID는 `통합계약번호/page-N/row-N`이며 페이지와 행은 1부터 센다. 같은 차수로 등록된 여러 통합계약번호는 품목 내용 일치를 확인해 한 벌만 채택했다. |
| 포털 계약정보서비스 URL, 물품상세 응답의 수집시각 | `source_url`, `retrieved_at`, `synthetic` | 데이터셋 URL, 시간대가 있는 원본 수집시각, false. |
| `prdctIdntNo`, `prdctClsfcNoNm`, `krnPrdctNm` | `item_id`, `item_name`, `specification`, `model` | 식별번호·원본 품명·한글품명(규격 설명)을 보존했다. 별도 모델은 확인되지 않아 null이다. |
| 계약 원장의 `dminsttList`, 상세의 `cntrctCnclsDate` | `agency_id`, `agency_name`, `purchased_at` | 계약의 실제 수요기관 코드·명칭과 계약체결일이다. 무안청사는 이 출처에서 6130769다. |
| `prdctQty`, `qtyUprcAmt`, `prdctAmt` | `quantity`, `unit_price`, `price_basis`, `currency`, `unit` | 수량과 원본 품목 단가를 십진 문자열로 기록한다. 단가는 KRW다. 품목금액은 대조용으로 보관하며, 수량의 단위는 원본에 없어 null이다. |
| `dcsnCntrctNo` 및 조회된 차수·삭제 기록 | `contract_id`, `revision`, `status` | 확정계약번호를 기초번호와 끝 두 자리 차수로 분리했다. 이행·지급은 미확인이므로 unknown이다. |
| 인도조건 등 상세 원문 | `tax_included`, `delivery_included`, `installation_included` | 각 비용이 단가에 포함됐는지 확인할 근거가 없어 null이다. |

연간 정제본의 모든 행은 `record_id`로 `purchase-sources.json`에서 찾을 수 있다. 이 파일의 `row_index`는 두 출처 모두 0부터 센다. 쇼핑몰 행은 `shopping-responses.tar.gz`, 보조 계약 행은 `supplemental-raw.tar.gz`에서 `raw_page`를 연다. `shopping-report-raw.tar.gz`와 `shopping-report-check.json`에는 조달데이터허브 보고서와 차수 재조회 근거가 있다. 원본은 모두 저장소의 로컬 보관 규칙을 따른다.
