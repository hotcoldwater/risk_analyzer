from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from typing import Any

import dart_fss as dart
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Risk Analyzer Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    corpCode: str
    corpName: str | None = None
    startYear: int
    endYear: int
    reportCode: str
    fsDiv: str


ACCOUNT_RULES: list[dict[str, Any]] = [
    {"key": "revenue", "concepts": {"ifrs-full_Revenue"}, "labels": ["매출액", "수익", "영업수익"]},
    {
        "key": "operatingProfit",
        "concepts": {"dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"},
        "labels": ["영업이익", "영업손익"],
    },
    {"key": "netIncome", "concepts": {"ifrs-full_ProfitLoss"}, "labels": ["당기순이익", "당기순손익"]},
    {
        "key": "operatingCashFlow",
        "concepts": {"ifrs-full_CashFlowsFromUsedInOperatingActivities"},
        "labels": ["영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업에서 창출된 현금흐름"],
    },
    {
        "key": "accountsReceivable",
        "concepts": {
            "ifrs-full_TradeAndOtherCurrentReceivables",
            "dart_ShortTermTradeReceivable",
        },
        "labels": ["매출채권 및 기타채권", "매출채권"],
    },
    {"key": "inventory", "concepts": {"ifrs-full_Inventories"}, "labels": ["재고자산"]},
    {"key": "intangibleAssets", "concepts": {"ifrs-full_IntangibleAssetsOtherThanGoodwill"}, "labels": ["무형자산"]},
    {"key": "totalAssets", "concepts": {"ifrs-full_Assets"}, "labels": ["자산총계"]},
    {"key": "totalLiabilities", "concepts": {"ifrs-full_Liabilities"}, "labels": ["부채총계"]},
    {"key": "totalEquity", "concepts": {"ifrs-full_Equity"}, "labels": ["자본총계"]},
]


def init_dart() -> str:
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="DART API 인증키가 설정되지 않았습니다.")
    dart.set_api_key(api_key=api_key)
    return api_key


@lru_cache(maxsize=1)
def get_corp_list():
    init_dart()
    return dart.get_corp_list()


def corp_to_summary(corp: Any) -> dict[str, Any]:
    return {
        "corpCode": getattr(corp, "corp_code", ""),
        "corpName": getattr(corp, "corp_name", ""),
        "stockCode": getattr(corp, "stock_code", None) or None,
        "modifyDate": getattr(corp, "modify_date", None) or None,
    }


def corp_to_profile(corp: Any) -> dict[str, Any]:
    return {
        "corpCode": getattr(corp, "corp_code", ""),
        "corpName": getattr(corp, "corp_name", ""),
        "stockCode": getattr(corp, "stock_code", None) or None,
        "corpClass": getattr(corp, "corp_cls", None) or None,
        "industryCode": getattr(corp, "induty_code", None) or None,
        "fiscalMonth": getattr(corp, "acc_mt", None) or None,
    }


def normalize_corp_name(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def report_code_to_type(report_code: str) -> str | list[str]:
    if report_code == "11011":
        return "annual"
    if report_code == "11012":
        return ["half"]
    if report_code in {"11013", "11014"}:
        return ["quarter"]
    return "annual"


def flatten_column_name(column: Any) -> str:
    if isinstance(column, tuple):
        for item in column:
            item_str = str(item)
            if re.match(r"^\d{8}(-\d{8})?$", item_str):
                return item_str
        return str(column[-1])
    return str(column)


def value_to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value or value == "-":
            return None
        if value.startswith("(") and value.endswith(")"):
            value = f"-{value[1:-1]}"
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def label_score(label: str, concept_id: str, rule: dict[str, Any]) -> int:
    normalized_label = re.sub(r"\s+", "", label).lower()
    score = 0
    if concept_id in rule["concepts"]:
        score += 100
    for index, candidate in enumerate(rule["labels"]):
        normalized_candidate = re.sub(r"\s+", "", candidate).lower()
        if normalized_label == normalized_candidate:
            score += 50 - index
            break
        if normalized_candidate in normalized_label:
            score += 20 - index
            break
    return score


def extract_year_columns(df: pd.DataFrame) -> list[tuple[Any, int]]:
    results: list[tuple[Any, int]] = []
    for column in df.columns:
        name = flatten_column_name(column)
        if re.match(r"^\d{8}$", name):
            results.append((column, int(name[:4])))
        elif re.match(r"^\d{8}-\d{8}$", name):
            results.append((column, int(name[:4])))
    return results


def normalize_financial_statement(
    fs: Any, start_year: int, end_year: int, fs_div: str, report_code: str
) -> list[dict[str, Any]]:
    years = {
        year: {
            "year": year,
            "fsDiv": fs_div,
            "reportCode": report_code,
        }
        for year in range(start_year, end_year + 1)
    }
    scores: dict[int, dict[str, int]] = {year: {} for year in years}

    for section_key in ["bs", "is", "cis", "cf"]:
        df = fs[section_key]
        if df is None:
            continue

        label_col = next((column for column in df.columns if flatten_column_name(column) == "label_ko"), None)
        concept_col = next((column for column in df.columns if flatten_column_name(column) == "concept_id"), None)
        if label_col is None or concept_col is None:
            continue

        for _, row in df.iterrows():
            label = str(row[label_col] or "")
            concept_id = str(row[concept_col] or "")
            for column, year in extract_year_columns(df):
                if year not in years:
                    continue
                number = value_to_number(row[column])
                if number is None:
                    continue
                for rule in ACCOUNT_RULES:
                    score = label_score(label, concept_id, rule)
                    if score <= (scores[year].get(rule["key"], -1)):
                        continue
                    if score == 0:
                        continue
                    scores[year][rule["key"]] = score
                    years[year][rule["key"]] = number

    return [years[year] for year in sorted(years)]


def calculate_debt_ratio(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        liabilities = item.get("totalLiabilities")
        equity = item.get("totalEquity")
        status = "ok"
        debt_ratio = None
        debt_ratio_percent = None
        if liabilities is None:
            status = "missing_liabilities"
        elif equity is None:
            status = "missing_equity"
        elif equity == 0:
            status = "zero_equity"
        else:
            debt_ratio = liabilities / equity
            debt_ratio_percent = debt_ratio * 100
        results.append(
            {
                "year": item["year"],
                "totalLiabilities": liabilities,
                "totalEquity": equity,
                "debtRatio": debt_ratio,
                "debtRatioPercent": debt_ratio_percent,
                "status": status,
            }
        )
    return results


def detect_account_surges(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    monitored = ["accountsReceivable", "inventory", "intangibleAssets", "revenue", "operatingCashFlow"]
    signals: list[dict[str, Any]] = []
    sorted_items = sorted(items, key=lambda item: item["year"])
    for current_index in range(1, len(sorted_items)):
        previous = sorted_items[current_index - 1]
        current = sorted_items[current_index]
        for key in monitored:
            prev_value = previous.get(key)
            curr_value = current.get(key)
            if prev_value in (None, 0) or curr_value is None:
                continue
            change_rate = (curr_value - prev_value) / abs(prev_value)
            if abs(change_rate) < 0.3:
                continue
            signals.append(
                {
                    "id": f"{key}-{current['year']}",
                    "year": current["year"],
                    "accountKey": key,
                    "title": f"{current['year']}년 계정 변동",
                    "description": f"{key} 계정이 전년 대비 {change_rate * 100:.1f}% 변동했습니다. 추가 검토가 필요할 수 있습니다.",
                    "severity": "high" if abs(change_rate) >= 0.5 else "medium",
                }
            )
    return signals


def analyze_cashflow_gap(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in items:
        net_income = item.get("netIncome")
        operating_cash_flow = item.get("operatingCashFlow")
        if net_income is None or operating_cash_flow is None:
            continue
        if net_income > 0 and operating_cash_flow < 0:
            signals.append(
                {
                    "id": f"cashflow-negative-{item['year']}",
                    "year": item["year"],
                    "accountKey": "operatingCashFlow",
                    "title": f"{item['year']}년 순이익-현금흐름 괴리",
                    "description": "순이익은 흑자이지만 영업활동현금흐름은 적자입니다. 이익의 질에 대한 추가 검토가 필요할 수 있습니다.",
                    "severity": "high",
                }
            )
        if net_income > 0 and operating_cash_flow / net_income < 0.5:
            signals.append(
                {
                    "id": f"cashflow-ratio-{item['year']}",
                    "year": item["year"],
                    "accountKey": "operatingCashFlow",
                    "title": f"{item['year']}년 현금창출력 약화",
                    "description": "영업활동현금흐름이 순이익 대비 낮게 나타났습니다. 수익 인식 또는 운전자본 변동 검토가 필요할 수 있습니다.",
                    "severity": "medium",
                }
            )
    return signals


def build_summary(financials: list[dict[str, Any]]) -> str:
    valid = [item for item in financials if item["debtRatioPercent"] is not None]
    if len(valid) < 2:
        return "분석기간 동안 부채비율 추이를 계산했습니다. 일부 연도는 데이터가 부족해 추가 검토가 필요합니다."
    first = valid[0]
    last = valid[-1]
    direction = "상승" if last["debtRatioPercent"] >= first["debtRatioPercent"] else "하락"
    return (
        f"분석기간 동안 부채비율은 {first['year']}년 {first['debtRatioPercent']:.1f}%에서 "
        f"{last['year']}년 {last['debtRatioPercent']:.1f}%로 {direction}했습니다. "
        "재무구조 변화에 대한 추가 검토가 필요할 수 있습니다."
    )


@app.get("/health")
def healthcheck():
    return {"ok": True}


@app.get("/search-company")
def search_company(query: str = Query(..., min_length=1)):
    try:
        corps = get_corp_list().find_by_corp_name(query, exactly=False, market="YKNE")
    except Exception as error:  # pragma: no cover - library error formatting
        raise HTTPException(status_code=500, detail=f"기업 검색 중 오류가 발생했습니다: {error}") from error

    normalized_query = normalize_corp_name(query)
    sorted_corps = sorted(
        corps,
        key=lambda corp: (
            0 if normalize_corp_name(getattr(corp, "corp_name", "")) == normalized_query else 1,
            0 if getattr(corp, "stock_code", None) else 1,
            getattr(corp, "corp_name", ""),
        ),
    )
    data = [corp_to_summary(corp) for corp in sorted_corps[:20]]
    return {"success": True, "data": data}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if request.startYear > request.endYear:
        raise HTTPException(status_code=400, detail="시작연도는 종료연도보다 클 수 없습니다.")

    corp_list = get_corp_list()
    corp = corp_list.find_by_corp_code(request.corpCode)
    if not corp:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")

    try:
        fs = dart.fs.extract(
            corp_code=request.corpCode,
            bgn_de=f"{request.startYear}0101",
            end_de=f"{request.endYear}1231",
            separate=request.fsDiv == "OFS",
            report_tp=report_code_to_type(request.reportCode),
            lang="ko",
            separator=True,
            dataset="web",
            cumulative=False,
            progressbar=False,
            skip_error=True,
            last_report_only=True,
            min_required=1,
        )
    except Exception as error:  # pragma: no cover - library error formatting
        raise HTTPException(status_code=500, detail=f"재무제표 조회 중 오류가 발생했습니다: {error}") from error

    normalized = normalize_financial_statement(fs, request.startYear, request.endYear, request.fsDiv, request.reportCode)
    financials = calculate_debt_ratio(normalized)
    yearly_status = [
        {
            "year": item["year"],
            "fetched": any(item.get(key) is not None for key in ("totalLiabilities", "totalEquity", "revenue", "netIncome")),
            "fsDivUsed": item["fsDiv"],
            "fallbackApplied": False,
            "error": None,
        }
        for item in normalized
    ]

    return {
        "success": True,
        "data": {
            "company": corp_to_profile(corp),
            "period": {
                "startYear": request.startYear,
                "endYear": request.endYear,
                "reportCode": request.reportCode,
                "fsDiv": request.fsDiv,
            },
            "financials": financials,
            "yearlyStatus": yearly_status,
            "riskSignals": [*detect_account_surges(normalized), *analyze_cashflow_gap(normalized)],
            "summary": build_summary(financials),
        },
    }
