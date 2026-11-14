"""Local fixture-only API. All returned purchase data is synthetic."""
import json
from datetime import date
from decimal import Decimal
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
    records = examples("agency")
    return {key: [{"id": value, "name": name} for value, name in
                  dict((a["target"][f"{field}_id"], a["target"][f"{field}_name"]) for a in records).items()]
            for key, field in (("agencies", "agency"), ("items", "item"))}


def examples(comparison_type):
    names = ["analysis.json", "analysis-insufficient.json", "analysis-unknown.json"] if comparison_type == "agency" else ["analysis-market.json"]
    return [fixture(name) for name in names]


def parameters(request, allowed):
    if any(key not in allowed for key in request.query_params):
        raise ValueError("unsupported field")
    if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise ValueError("duplicate field")
    params = dict(request.query_params)
    if params.get("comparison_type", "agency") not in ("agency", "market"):
        raise ValueError("invalid comparison type")
    return params


@app.get("/api/purchases")
def purchases(request: Request):
    try:
        params = parameters(request, {"q", "agency_id", "item_id", "comparison_type", "status", "sort", "page", "page_size", "date_from", "date_to"})
        query = params.get("q", "").strip().casefold()
        if len(query) > 200:
            raise ValueError("query too long")
        status = params.get("status")
        if status is not None and status not in {"comparable", "insufficient_data", "conditions_unknown", "unavailable"}:
            raise ValueError("invalid status")
        sort = params.get("sort", "purchased_desc")
        if sort not in {"purchased_desc", "difference_pct_desc"} or (sort == "difference_pct_desc" and not params.get("item_id")):
            raise ValueError("invalid sort")
        page, size = int(params.get("page", "1")), int(params.get("page_size", "20"))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError("invalid page")
        start, end = params.get("date_from"), params.get("date_to")
        for value in (start, end):
            if value and date.fromisoformat(value).isoformat() != value:
                raise ValueError("invalid date")
        if start and end and start > end:
            raise ValueError("reversed dates")
        records = examples(params.get("comparison_type", "agency"))
        records = [a for a in records if
                   (not query or any(query in str(a["target"].get(key) or "").casefold() for key in ("item_name", "model", "agency_name")))
                   and all(not params.get(f"{field}_id") or a["target"][f"{field}_id"] == params[f"{field}_id"] for field in ("agency", "item"))
                   and (not status or a["status"] == status)
                   and (not start or (a["target"]["purchased_at"] and a["target"]["purchased_at"] >= start))
                   and (not end or (a["target"]["purchased_at"] and a["target"]["purchased_at"] <= end))]
        records.sort(key=lambda a: a["record_id"])
        if sort == "difference_pct_desc":
            records.sort(key=lambda a: (a["difference_pct"] is None, -Decimal(a["difference_pct"] or "0")))
        else:
            records.sort(key=lambda a: a["target"]["purchased_at"] or "", reverse=True)
        return {"contract_version": "1.0", "dataset_version": "synthetic-v1", "synthetic": True,
                "items": records[(page - 1) * size:page * size], "total": len(records), "page": page, "page_size": size}
    except (ValueError, TypeError):
        return error(400, "INVALID_REQUEST", "검색 조건·날짜·정렬 또는 페이지 값을 확인하세요.")


@app.get("/api/purchases/{record_id}")
def purchase(record_id: str, request: Request):
    try:
        params = parameters(request, {"comparison_type"})
    except ValueError:
        return error(400, "INVALID_REQUEST", "비교 유형을 확인하세요.")
    for analysis in examples(params.get("comparison_type", "agency")):
        if analysis["record_id"] == record_id:
            return analysis
    return error(404, "NOT_FOUND", "해당 비교 유형의 구매 기록을 찾을 수 없습니다.")
