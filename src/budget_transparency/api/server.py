"""Local fixture-only API. All returned purchase data is synthetic."""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "contracts-v1"
app = FastAPI(title="공공계약 비교 API — 합성 예제", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def fixture(name: str):
    with (FIXTURES / name).open(encoding="utf-8") as file:
        return json.load(file)


def error(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.get("/")
def root():
    return {"message": "합성 예제 API입니다. 실제 구매 데이터가 아닙니다.", "synthetic": True, "docs": "/docs"}


@app.get("/api/options")
def options():
    # Only the record with an implemented detail response is offered for now.
    return {"agencies": [{"id": "agency-A", "name": "예시기관 A"}],
            "items": [{"id": "demo-item-1", "name": "예시 물품"}]}


@app.get("/api/purchases")
def purchases(request: Request):
    if request.query_params:
        return error(400, "INVALID_REQUEST", "검색·필터는 아직 지원하지 않습니다.")
    return fixture("list.json")


@app.get("/api/purchases/{record_id}")
def purchase(record_id: str, request: Request):
    if request.query_params:
        return error(400, "INVALID_REQUEST", "비교 유형 선택은 아직 지원하지 않습니다.")
    if record_id != "demo-A":
        return error(404, "NOT_FOUND", "구매 기록을 찾을 수 없습니다.")
    return fixture("analysis.json")
