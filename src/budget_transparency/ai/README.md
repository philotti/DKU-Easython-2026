# AI 모듈 (C)

질문을 검색 조건으로 바꾸고(`query.py`), 분석 결과에 설명을 붙입니다(`explain.py`). AI가 없거나 실패해도 기본 규칙·기본 안내로 동작합니다. 실행 결과 기록은 [ai-check.md](../../../docs/evidence/ai-check.md)에 있습니다.

## Gemini 키를 로컬에서 설정하기

키는 저장소 루트의 `.env` 파일에만 둡니다. `.env`는 `.gitignore`에 들어 있어 커밋되지 않습니다. 키를 코드·문서·메신저·PR에 붙여넣지 않습니다.

```bash
cp -n .env.example .env
```

`-n`은 이미 `.env`가 있으면 덮어쓰지 않는 옵션입니다. `.env`가 이미 있다면 복사하지 말고 그 파일에 아래 두 값만 추가합니다. 덮어쓰면 입력해 둔 키가 지워집니다.

`.env`를 열어 두 값을 입력합니다. 모델 ID는 E와 정한 값을 씁니다.

```text
GEMINI_API_KEY=발급받은 키
GEMINI_MODEL=사용할 모델 ID
```

## 코드에서 쓰기

```python
from budget_transparency.ai import gemini
from budget_transparency.ai.explain import explain_analysis
from budget_transparency.ai.query import parse_query

gemini.load_env()                   # .env를 환경 변수로 읽음. 이미 설정된 값은 덮어쓰지 않음
generate = gemini.make_generate()   # 키나 모델 ID가 없으면 None

parse_query("경기도의 운영체제", options, generate)
explain_analysis(analysis, generate)
```

`generate`가 `None`이거나, 호출이 실패하거나, 응답이 검증을 통과하지 못하면 결과의 `mode`가 `fallback`입니다. 키는 요청 헤더로만 보내고 URL·로그·오류 메시지에 넣지 않습니다. 리디렉션은 따라가지 않으므로 키가 다른 주소로 전달되지 않습니다. 별도 SDK 없이 표준 라이브러리로 호출합니다.

## 실제 모델로 확인하기

```bash
python3 scripts/check_ai_live.py          # 합성 예제 목록
python3 scripts/check_ai_live.py --real   # 실제 시연 데이터 목록
```

질문별 조건, 설명, 모델 원문, 호출 성공 여부와 걸린 시간을 출력합니다. 실제 호출이므로 자동 테스트와 CI에는 포함하지 않습니다. 결과를 읽고 ai-check.md에 기록합니다.
