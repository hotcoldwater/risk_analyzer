from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.analyzer import calculate_debt_ratio
from app.cache import build_cache_key, get_cached_analysis, set_cached_analysis
from app.config import get_settings
from app.database import initialize_database
from app.dart_client import CorporationNotFoundError, find_corporation, initialize_dart
from app.financial_extractor import FinancialDataError, extract_latest_liabilities_and_equity
from app.samsung_financials import get_samsung_financial_statements, sync_samsung_financial_statements
from app.schemas import (
    DebtRatioResponse,
    ErrorResponse,
    FinancialStatementRecord,
    SamsungFinancialStatementsResponse,
    SamsungFinancialStatementsSyncResponse,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_dart()
    initialize_database()
    yield


app = FastAPI(
    title="DART Financial Risk Analyzer API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, message: str, detail: str | None = None) -> JSONResponse:
    payload = ErrorResponse(message=message, detail=detail)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(422, "요청 형식이 올바르지 않습니다.", str(exc))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return _error_response(500, "분석 중 오류가 발생했습니다.", str(exc))


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "DART Financial Risk Analyzer API",
        "status": "ok",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get(
    "/api/debt-ratio",
    response_model=DebtRatioResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_debt_ratio(query: str) -> DebtRatioResponse:
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(status_code=400, detail="기업명 또는 기업번호를 입력해 주세요.")

    cache_key = build_cache_key(normalized_query, "debt-ratio")
    cached_payload = get_cached_analysis(cache_key)
    if cached_payload is not None:
        return DebtRatioResponse(**cached_payload, cached=True)

    try:
        corporation_match = find_corporation(normalized_query)
        extraction = extract_latest_liabilities_and_equity(corporation_match.corp)
        debt_ratio = calculate_debt_ratio(extraction.liabilities, extraction.equity)
    except CorporationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FinancialDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = {
        "corpName": corporation_match.corp.corp_name,
        "corpCode": corporation_match.corp.corp_code,
        "year": extraction.year,
        "liabilities": extraction.liabilities,
        "equity": extraction.equity,
        "debtRatio": debt_ratio,
        "unit": extraction.unit,
        "source": "DART",
        "warnings": corporation_match.warnings,
    }

    set_cached_analysis(cache_key, payload)
    return DebtRatioResponse(**payload, cached=False)


@app.post(
    "/api/db/samsung-financial-statements/sync",
    response_model=SamsungFinancialStatementsSyncResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def sync_samsung_financials() -> SamsungFinancialStatementsSyncResponse:
    try:
        result = sync_samsung_financial_statements()
    except CorporationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FinancialDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SamsungFinancialStatementsSyncResponse(
        corpName=result.corp_name,
        corpCode=result.corp_code,
        inserted=result.inserted,
        updated=result.updated,
        total=result.total,
        years=result.years,
    )


@app.get(
    "/api/db/samsung-financial-statements",
    response_model=SamsungFinancialStatementsResponse,
    responses={404: {"model": ErrorResponse}},
)
def list_samsung_financials() -> SamsungFinancialStatementsResponse:
    rows = get_samsung_financial_statements()
    if not rows:
        raise HTTPException(status_code=404, detail="DB에 저장된 삼성전자 재무제표가 없습니다. 먼저 동기화를 실행해 주세요.")

    first_row = rows[0]
    return SamsungFinancialStatementsResponse(
        corpName=first_row["corp_name"],
        corpCode=first_row["corp_code"],
        count=len(rows),
        items=[FinancialStatementRecord(**row) for row in rows],
    )
