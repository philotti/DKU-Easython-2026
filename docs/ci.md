# CI — PR을 올리면 자동으로 확인하기

CI는 GitHub가 변경된 파일에 대해 정해진 검사를 실행하는 기능입니다. 설정은 `.github/workflows/ci.yml`입니다. push·PR·수동 실행에 동작하도록 준비했으며 아직 GitHub 실행을 확인한 것은 아닙니다. 로컬 검사만 수행했습니다.

## 현재 검사

- Markdown 상대 링크
- 계약 v1 합성 예제 15개의 스키마와 적용 가능한 계산·참조 규칙
- `data/demo/`에 제출한 JSON 형식, ID 중복, 실제/합성 혼합, 출처 정보
- 검증기가 잘못된 입력을 거절하는지 확인하는 9개 테스트

외부 Gemini·나라장터 호출과 키는 필요하지 않습니다. 원본 데이터의 진실성이나 화면 완성도는 자동 보장하지 않습니다. 웹 빌드·분석 함수 테스트·통합 테스트는 실제 코드와 실행 환경이 생긴 뒤 E가 추가합니다.

## 팀원이 데이터 제출하기

자동 검사 대상 이름은 `data/demo/purchases.json`, `data/demo/market-prices.json`, `data/demo/comparison-policy.json`입니다. 다른 JSON 경로는 검사 누락을 막기 위해 실패 처리합니다. 자료가 아직 없으면 없다고 표시하고 통과하므로 초록 체크가 데이터 준비 완료를 뜻하지는 않습니다.

임시 이름의 파일을 먼저 검사하려면:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/check_data.py --file /path/to/purchases.json --schema purchases
```

시중가에는 `--schema market-prices`, 정책에는 `--schema policy`를 씁니다. 저장소의 제출 자료 전체는 `python3 scripts/check_data.py`로 검사합니다. 실제 데이터라도 결측을 억지로 채우지 않으며 원본 대조는 A·B가 별도로 합니다.

## PR에 빨간 체크가 나오면

PR의 Checks에서 실패한 단계와 로그를 확인합니다. 필드 오류는 A·E, 계산 예제는 B, 문서 링크는 수정자에게 요청합니다. 수정 커밋을 push하면 다시 검사됩니다. 오류를 없애려고 검사를 끄거나 계약을 무단 변경하지 않습니다.

## E가 GitHub에서 마무리할 것

설정 파일을 포함해 push한 뒤 Actions에서 실행 여부를 확인합니다. 저장소의 Actions 허용 상태도 확인합니다. 통과 후 main 브랜치 ruleset/보호 규칙에서 `contracts-and-docs`를 필수 검사로 지정하고 PR 머지를 요구하도록 설정할 수 있습니다. **워크플로 파일만 추가하면 빨간 체크가 머지를 자동으로 차단하는 것은 아닙니다.** 브랜치 보호 설정은 아직 적용하지 않았습니다.

공식 참고: [GitHub의 Python CI 안내](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
