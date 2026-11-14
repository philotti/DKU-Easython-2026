# 합성 예제 API 서버

공통 계약의 합성 JSON을 그대로 반환하는 **임시 개발용 서버**입니다. 실제 공공데이터, 가격 계산, 자연어 검색, Gemini는 연결되지 않았습니다. 카드 한 건에 해당하는 응답만 제공합니다.

| 주소 | 반환 내용 |
|---|---|
| `GET /` | 서버 안내와 합성 자료 표시 |
| `GET /api/options` | 이 서버가 제공하는 예제 기관·물품 |
| `GET /api/purchases` | `list.json`의 예제 구매 목록 |
| `GET /api/purchases/demo-A` | `analysis.json`의 예제 상세 |

존재하지 않는 구매 ID는 404이며, 아직 구현하지 않은 검색·필터 쿼리는 400입니다. 계약 v1의 전체 검색·정렬·비교 유형·AI 경로는 구현 예정입니다. 대상 가격·비교값은 파일에 미리 기록된 합성값이므로 실시간 계산으로 설명하지 않습니다.

## 설치와 실행

macOS/Linux, 저장소 루트 기준:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-server.txt
.venv/bin/python -m uvicorn budget_transparency.api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

Windows PowerShell, 저장소 루트 기준:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-server.txt
.venv\Scripts\python.exe -m uvicorn budget_transparency.api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000/api/purchases`를 열면 JSON이 보입니다. 개발 중인 React 화면의 기본 주소 `http://localhost:5173` 또는 `http://127.0.0.1:5173`에서 GET 호출을 허용합니다. 실제 화면 주소가 다르면 E가 CORS 설정을 확인합니다. 외부 접속·배포용 설정은 아닙니다.

서버를 종료하려면 실행 중인 터미널에서 Ctrl+C를 누릅니다. 8000 포트를 이미 쓰고 있다면 `--port 8001`로 바꾸고 브라우저 주소도 같이 변경합니다.

## 검사

```bash
.venv/bin/python -m unittest discover -s tests/unit -p 'test_fixture_server.py' -v
```

Windows는 `.venv\Scripts\python.exe`로 바꿉니다. 검사는 합성 목록·상세 일치, 없는 ID와 미구현 필터의 오류, 선택지 응답을 확인합니다.
