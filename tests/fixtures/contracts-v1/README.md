# 계약 v1 합성 예제

모든 기관·물품·판매처·가격은 합성입니다. 실제 낭비·절감 사례가 아닙니다. 정상 서버가 실제로 응답했다는 뜻도 아닙니다.

| 역할 | 열 파일 |
|---|---|
| A | purchases.json, market-prices.json (정규화 모양) |
| B | policy.json, analysis.json, analysis-market.json (입력·정답) |
| C | query.json, explanation.json (기본 안내 응답) |
| D | list.json, analysis.json, analysis-insufficient.json, analysis-unknown.json, analysis-no-market.json, analysis-unavailable.json, list-empty.json, options.json |
| E | 전체 파일·manifest.json·error.json |

analysis.json은 예시기관 A의 150000원과 다른 세 기관 중앙값 120000원을 비교해 30000원·25.00%를 반환합니다. analysis-market.json은 별도 합성 시중가 110000원과 비교합니다. analysis-no-market.json은 빈 시중가 배열을 넣는 시나리오, analysis-unavailable.json은 대상 상태를 cancelled로 바꾼 시나리오입니다. 정상 입력과 다른 조건을 의도적으로 표현합니다.

검사: 저장소 루트에서 `python3 scripts/check_contracts.py`. manifest.json은 예제 파일과 검증 스키마 대응표입니다. 실제 데이터와 섞지 마세요.
