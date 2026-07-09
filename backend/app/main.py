from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import initialize_database
from app.defense_service import (
    get_anomaly_analysis,
    get_company_profile,
    get_liquidity_metric,
    resolve_company,
    search_companies,
)
from app.schemas import (
    AnomalyAnalysisResponse,
    CompanyProfileResponse,
    CompanySuggestion,
    ErrorResponse,
    LiquidityMetricResponse,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Defense Cash Conversion Analyzer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.risk-analyzer\.pages\.dev|https://.*\.pages\.dev|http://localhost:5173|http://localhost:3000",
    allow_origins=[settings.frontend_origin],
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
    return {"service": "Defense Cash Conversion Analyzer API", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get(
    "/api/company-search",
    response_model=list[CompanySuggestion],
    responses={500: {"model": ErrorResponse}},
)
def company_search(q: str) -> list[CompanySuggestion]:
    items = search_companies(settings.supabase_database_url, q)
    return [
        CompanySuggestion(
            companyId=item["corp_code"],
            companyName=item["corp_name"],
            stockCode=item["stock_code"],
            market=item.get("market"),
        )
        for item in items
    ]


@app.get(
    "/api/company-resolve",
    response_model=CompanyProfileResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def company_resolve(query: str) -> CompanyProfileResponse:
    match = resolve_company(settings.supabase_database_url, query)
    if match is None:
        raise HTTPException(status_code=404, detail="해당 기업정보가 존재하지 않습니다.")
    return CompanyProfileResponse(**get_company_profile(settings.supabase_database_url, match["corp_code"]))


@app.get(
    "/api/company-profile",
    response_model=CompanyProfileResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def company_profile(corp_code: str) -> CompanyProfileResponse:
    try:
        payload = get_company_profile(settings.supabase_database_url, corp_code)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CompanyProfileResponse(**payload)


@app.get(
    "/api/analysis/liquidity-metric",
    response_model=LiquidityMetricResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def liquidity_metric(corp_code: str, metric_code: str, group_scope: str = "A") -> LiquidityMetricResponse:
    try:
        payload = get_liquidity_metric(
            settings.supabase_database_url,
            corp_code=corp_code,
            metric_code=metric_code,
            group_scope=group_scope,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LiquidityMetricResponse(**payload)


@app.get(
    "/api/analysis/anomaly",
    response_model=AnomalyAnalysisResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def anomaly_analysis(corp_code: str, group_scope: str = "A") -> AnomalyAnalysisResponse:
    try:
        payload = get_anomaly_analysis(settings.supabase_database_url, corp_code=corp_code, group_scope=group_scope)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnomalyAnalysisResponse(**payload)
