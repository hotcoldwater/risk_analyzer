from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row


YEARS = [2021, 2022, 2023, 2024, 2025]
CURRENT_YEAR = 2025

GROUP_SCOPES = {
    "A": {"A"},
    "AB": {"A", "B"},
    "ABC": {"A", "B", "C"},
}

LIQUIDITY_METRICS = {
    "revenue_growth": {
        "name": "매출액 증가율",
        "description": "외형 성장",
        "accounts": ["매출액"],
    },
    "operating_margin": {
        "name": "영업이익률",
        "description": "본업 수익성",
        "accounts": ["매출액", "영업이익"],
    },
    "cfo_conversion": {
        "name": "영업활동현금흐름 전환율",
        "description": "이익의 현금화 수준",
        "accounts": ["영업이익", "영업활동현금흐름"],
    },
    "contract_asset_ratio": {
        "name": "계약자산비율",
        "description": "미청구·미회수 성격의 부담",
        "accounts": ["매출액", "계약자산"],
    },
    "net_contract_asset_ratio": {
        "name": "순계약자산비율",
        "description": "수익인식과 청구 간 괴리",
        "accounts": ["매출액", "계약자산", "계약부채"],
    },
}

TARGET_ACCOUNTS = [
    "매출액",
    "영업이익",
    "영업활동현금흐름",
    "계약자산",
    "계약부채",
    "매출채권",
    "재고자산",
]

ANALYSIS_LABELS = [
    {"code": "liquidity_risk", "name": "현금화 리스크 분석", "ready": True},
    {"code": "growth", "name": "성장성 분석", "ready": False},
    {"code": "dev_inventory_provision", "name": "개발비·재고·충당부채 리스크 분석", "ready": False},
    {"code": "anomaly", "name": "이상징후 분석", "ready": True},
]


@dataclass(frozen=True)
class CompanyRecord:
    corp_code: str
    stock_code: str
    corp_name: str
    market: str | None
    memo: str | None


@dataclass(frozen=True)
class GroupRecord:
    industry_id: str
    level: str
    level_category: str | None
    is_primary: bool


def _connect(database_url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(database_url, row_factory=dict_row)


def _format_source_label(fs_div: str | None) -> str:
    if fs_div == "CFS":
        return "연결 기준(CFS)"
    if fs_div == "OFS":
        return "별도 기준(OFS)"
    return "출처 없음"


def _safe_div(numerator: float | None, denominator: float | None, multiplier: float = 1.0) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * multiplier


def _growth_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / previous * 100


def _pp_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def search_companies(database_url: str, query: str) -> list[dict[str, Any]]:
    normalized = query.strip()
    if not normalized:
        return []

    like_query = f"%{normalized}%"
    starts_query = f"{normalized}%"
    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT corp_code, stock_code, corp_name, market
            FROM public.companies_basic
            WHERE corp_name ILIKE %(like)s
               OR stock_code ILIKE %(like)s
               OR corp_code ILIKE %(like)s
            ORDER BY
                CASE
                    WHEN corp_name = %(exact)s THEN 0
                    WHEN stock_code = %(exact)s THEN 1
                    WHEN corp_code = %(exact)s THEN 2
                    WHEN corp_name ILIKE %(starts)s THEN 3
                    ELSE 4
                END,
                corp_name
            LIMIT 8
            """,
            {"like": like_query, "starts": starts_query, "exact": normalized},
        )
        return [dict(row) for row in cursor.fetchall()]


def resolve_company(database_url: str, query: str) -> dict[str, Any] | None:
    normalized = query.strip()
    if not normalized:
        return None

    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT corp_code, stock_code, corp_name, market, memo
            FROM public.companies_basic
            WHERE corp_name = %(query)s
               OR stock_code = %(query)s
               OR corp_code = %(query)s
            ORDER BY CASE
                WHEN corp_name = %(query)s THEN 0
                WHEN stock_code = %(query)s THEN 1
                ELSE 2
            END
            LIMIT 1
            """,
            {"query": normalized},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)


def get_company_profile(database_url: str, corp_code: str) -> dict[str, Any]:
    with _connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT corp_code, stock_code, corp_name, market, memo
            FROM public.companies_basic
            WHERE corp_code = %(corp_code)s
            """,
            {"corp_code": corp_code},
        )
        company = cursor.fetchone()
        if company is None:
            raise LookupError("해당 기업정보가 존재하지 않습니다.")

        cursor.execute(
            """
            SELECT industry_id, level, level_category, is_primary
            FROM public.industry_map
            WHERE corp_code = %(corp_code)s
            ORDER BY industry_id, level
            """,
            {"corp_code": corp_code},
        )
        groups = [dict(row) for row in cursor.fetchall()]

    return {
        "company": dict(company),
        "groups": groups,
        "analyses": ANALYSIS_LABELS,
    }


def _fetch_company_levels(connection: psycopg.Connection[Any], industry_id: str) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT corp_code, level
            FROM public.industry_map
            WHERE industry_id = %(industry_id)s
            """,
            {"industry_id": industry_id},
        )
        return {row["corp_code"]: row["level"] for row in cursor.fetchall()}


def _fetch_financial_rows(
    connection: psycopg.Connection[Any],
    table_name: str,
    corp_codes: list[str],
    accounts: list[str],
) -> list[dict[str, Any]]:
    if not corp_codes:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT corp_code, stock_code, corp_name, year, fs_div, sj_div, account_name, amount, memo, updated_at
            FROM public.{table_name}
            WHERE corp_code = ANY(%(corp_codes)s)
              AND year = ANY(%(years)s)
              AND account_name = ANY(%(accounts)s)
            ORDER BY corp_code, year, fs_div NULLS LAST, account_name
            """,
            {"corp_codes": corp_codes, "years": YEARS, "accounts": accounts},
        )
        return [dict(row) for row in cursor.fetchall()]


def _build_company_year_index(rows: list[dict[str, Any]]) -> dict[str, dict[int, list[dict[str, Any]]]]:
    index: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for row in rows:
        index.setdefault(row["corp_code"], {}).setdefault(int(row["year"]), []).append(row)
    return index


def _select_basis(rows: list[dict[str, Any]], required_accounts: list[str]) -> str | None:
    required = set(required_accounts)
    actual_by_basis = {
        "CFS": {row["account_name"] for row in rows if row["fs_div"] == "CFS" and row["amount"] is not None},
        "OFS": {row["account_name"] for row in rows if row["fs_div"] == "OFS" and row["amount"] is not None},
    }
    if required.issubset(actual_by_basis["CFS"]):
        return "CFS"
    if required.issubset(actual_by_basis["OFS"]):
        return "OFS"
    if actual_by_basis["CFS"] & required:
        return "CFS"
    if actual_by_basis["OFS"] & required:
        return "OFS"
    if actual_by_basis["CFS"]:
        return "CFS"
    if actual_by_basis["OFS"]:
        return "OFS"
    return None


def _extract_year_snapshot(rows: list[dict[str, Any]], required_accounts: list[str]) -> dict[str, Any]:
    basis = _select_basis(rows, required_accounts)
    basis_rows = [row for row in rows if row["fs_div"] == basis] if basis else []
    placeholder_rows = [row for row in rows if row["fs_div"] is None]
    values: dict[str, float | None] = {}
    notes: dict[str, str | None] = {}

    for account_name in required_accounts:
        actual = next((row for row in basis_rows if row["account_name"] == account_name), None)
        placeholder = next((row for row in placeholder_rows if row["account_name"] == account_name), None)
        values[account_name] = float(actual["amount"]) if actual and actual["amount"] is not None else None
        notes[account_name] = (
            actual["memo"]
            if actual and actual.get("memo")
            else placeholder.get("memo")
            if placeholder
            else None
        )

    return {
        "basis": basis,
        "source_label": _format_source_label(basis),
        "values": values,
        "notes": notes,
    }


def _series_for_company(company_years: dict[int, list[dict[str, Any]]], accounts: list[str]) -> dict[int, dict[str, Any]]:
    series: dict[int, dict[str, Any]] = {}
    for year in YEARS:
        rows = company_years.get(year, [])
        series[year] = _extract_year_snapshot(rows, accounts)
    return series


def _metric_value(metric_code: str, current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> float | None:
    current = current_snapshot["values"]
    previous = previous_snapshot["values"] if previous_snapshot else {}

    if metric_code == "revenue_growth":
        return _growth_pct(current.get("매출액"), previous.get("매출액"))
    if metric_code == "operating_margin":
        return _safe_div(current.get("영업이익"), current.get("매출액"), 100)
    if metric_code == "cfo_conversion":
        return _safe_div(current.get("영업활동현금흐름"), current.get("영업이익"))
    if metric_code == "contract_asset_ratio":
        return _safe_div(current.get("계약자산"), current.get("매출액"), 100)
    if metric_code == "net_contract_asset_ratio":
        contract_assets = current.get("계약자산")
        contract_liabilities = current.get("계약부채")
        if contract_assets is None or contract_liabilities is None:
            return None
        return _safe_div(contract_assets - contract_liabilities, current.get("매출액"), 100)
    raise ValueError(f"Unknown metric: {metric_code}")


def _metric_reason(metric_code: str, current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> str | None:
    current = current_snapshot["values"]
    previous = previous_snapshot["values"] if previous_snapshot else {}
    notes = current_snapshot["notes"]

    if metric_code == "revenue_growth":
        if current.get("매출액") is None:
            return notes.get("매출액") or "2025년 매출액 데이터가 없습니다."
        previous_value = previous.get("매출액")
        if previous_value is None:
            return (previous_snapshot or {}).get("notes", {}).get("매출액") or "2024년 매출액 데이터가 없습니다."
        if previous_value <= 0:
            return "전년도 매출액이 0 이하라 증가율을 계산할 수 없습니다."
        return None

    for account in LIQUIDITY_METRICS[metric_code]["accounts"]:
        if current.get(account) is None:
            return notes.get(account) or f"2025년 {account} 데이터가 없습니다."

    if metric_code == "cfo_conversion" and current.get("영업이익") == 0:
        return "영업이익이 0이라 현금흐름 전환율을 계산할 수 없습니다."
    if metric_code in {"operating_margin", "contract_asset_ratio", "net_contract_asset_ratio"} and current.get("매출액") in {0, None}:
        return "매출액이 0이거나 없어 비율을 계산할 수 없습니다."
    return None


def _format_percent(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}%"


def _format_ratio(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}x"


def _format_currency(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.0f}원"


def _format_metric_display(metric_code: str, value: float | None) -> str:
    if metric_code in {"revenue_growth", "operating_margin", "contract_asset_ratio", "net_contract_asset_ratio"}:
        return _format_percent(value)
    if metric_code == "cfo_conversion":
        return _format_ratio(value)
    return "N/A"


def _metric_detail_rows(metric_code: str, series: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    current_snapshot = series[CURRENT_YEAR]
    previous_snapshot = series.get(CURRENT_YEAR - 1)
    current = current_snapshot["values"]
    previous = previous_snapshot["values"] if previous_snapshot else {}
    details = []

    for account in sorted(set(LIQUIDITY_METRICS[metric_code]["accounts"])):
        details.append(
            {
                "label": account,
                "currentValue": current.get(account),
                "currentDisplay": _format_currency(current.get(account)),
                "previousValue": previous.get(account),
                "previousDisplay": _format_currency(previous.get(account)),
                "note": current_snapshot["notes"].get(account) or (previous_snapshot or {}).get("notes", {}).get(account),
            }
        )

    details.append(
        {
            "label": "데이터 출처",
            "currentValue": current_snapshot["basis"],
            "currentDisplay": current_snapshot["source_label"],
            "previousValue": previous_snapshot["basis"] if previous_snapshot else None,
            "previousDisplay": previous_snapshot["source_label"] if previous_snapshot else "출처 없음",
            "note": "연결재무제표(CFS) 우선, 없으면 별도재무제표(OFS)를 사용합니다.",
        }
    )
    return details


def _average_series(
    metric_code: str,
    peer_codes: list[str],
    company_index: dict[str, dict[int, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    points = []
    accounts = LIQUIDITY_METRICS[metric_code]["accounts"]
    for year in YEARS:
        values: list[float] = []
        for corp_code in peer_codes:
            series = _series_for_company(company_index.get(corp_code, {}), accounts)
            current_snapshot = series[year]
            previous_snapshot = series.get(year - 1)
            value = _metric_value(metric_code, current_snapshot, previous_snapshot)
            if value is not None:
                values.append(value)
        average = sum(values) / len(values) if values else None
        points.append({"year": year, "averageValue": average, "sampleSize": len(values)})
    return points


def get_liquidity_metric(
    database_url: str,
    corp_code: str,
    metric_code: str,
    group_scope: str,
) -> dict[str, Any]:
    if metric_code not in LIQUIDITY_METRICS:
        raise ValueError("지원하지 않는 지표입니다.")
    if group_scope not in GROUP_SCOPES:
        raise ValueError("비교 그룹 범위가 올바르지 않습니다.")

    metric_definition = LIQUIDITY_METRICS[metric_code]
    with _connect(database_url) as connection:
        company_levels = _fetch_company_levels(connection, "defense")
        if corp_code not in company_levels:
            raise LookupError("방산 분석 대상 기업이 아닙니다.")

        level_scope = GROUP_SCOPES[group_scope]
        peer_codes = [code for code, level in company_levels.items() if level in level_scope]
        rows = _fetch_financial_rows(connection, "defense", [corp_code, *peer_codes], TARGET_ACCOUNTS)
        company_index = _build_company_year_index(rows)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT corp_code, stock_code, corp_name, market, memo
                FROM public.companies_basic
                WHERE corp_code = %(corp_code)s
                """,
                {"corp_code": corp_code},
            )
            company = cursor.fetchone()
            if company is None:
                raise LookupError("해당 기업정보가 존재하지 않습니다.")

    company_series = _series_for_company(company_index.get(corp_code, {}), metric_definition["accounts"])
    current_snapshot = company_series[CURRENT_YEAR]
    previous_snapshot = company_series.get(CURRENT_YEAR - 1)
    current_value = _metric_value(metric_code, current_snapshot, previous_snapshot)
    current_reason = _metric_reason(metric_code, current_snapshot, previous_snapshot)
    average_points = _average_series(metric_code, peer_codes, company_index)

    series = []
    for year in YEARS:
        snapshot = company_series[year]
        prev_snapshot = company_series.get(year - 1)
        avg_point = next(point for point in average_points if point["year"] == year)
        value = _metric_value(metric_code, snapshot, prev_snapshot)
        series.append(
            {
                "year": year,
                "companyValue": value,
                "companyDisplay": _format_metric_display(metric_code, value),
                "averageValue": avg_point["averageValue"],
                "averageDisplay": _format_metric_display(metric_code, avg_point["averageValue"]),
                "sampleSize": avg_point["sampleSize"],
                "sourceBasis": snapshot["basis"],
                "sourceLabel": snapshot["source_label"],
                "reason": _metric_reason(metric_code, snapshot, prev_snapshot),
            }
        )

    current_average = next(point for point in average_points if point["year"] == CURRENT_YEAR)
    return {
        "company": dict(company),
        "metricCode": metric_code,
        "metricName": metric_definition["name"],
        "metricDescription": metric_definition["description"],
        "year": CURRENT_YEAR,
        "groupScope": group_scope,
        "sourceBasis": current_snapshot["basis"],
        "sourceLabel": current_snapshot["source_label"],
        "currentValue": current_value,
        "currentDisplay": _format_metric_display(metric_code, current_value),
        "currentReason": current_reason,
        "averageValue": current_average["averageValue"],
        "averageDisplay": _format_metric_display(metric_code, current_average["averageValue"]),
        "averageSampleSize": current_average["sampleSize"],
        "series": series,
        "details": _metric_detail_rows(metric_code, company_series),
        "formula": metric_definition["description"],
    }


def _contract_asset_risk(company_series: dict[int, dict[str, Any]]) -> dict[str, Any]:
    current_snapshot = company_series[CURRENT_YEAR]
    previous_snapshot = company_series.get(CURRENT_YEAR - 1)
    current_values = current_snapshot["values"]
    previous_values = previous_snapshot["values"] if previous_snapshot else {}

    revenue_t = current_values.get("매출액")
    revenue_prev = previous_values.get("매출액")
    contract_assets_t = current_values.get("계약자산")
    contract_assets_prev = previous_values.get("계약자산")

    note_parts: list[str] = []
    revenue_growth = _growth_pct(revenue_t, revenue_prev)
    if revenue_prev is None:
        note_parts.append("전년도 매출액이 없어 매출액 증가율 계산이 제한됩니다.")
    elif revenue_prev <= 0:
        note_parts.append("전년도 매출액이 0 이하라 매출액 증가율을 계산하지 않았습니다.")

    newly_generated = False
    contract_asset_growth = None
    if contract_assets_prev is None:
        note_parts.append("전년도 계약자산이 없어 계약자산 증가율을 계산하지 않았습니다.")
    elif contract_assets_prev == 0 and (contract_assets_t or 0) > 0:
        newly_generated = True
        note_parts.append("전년도 계약자산이 0이어서 계약자산 증가율 대신 신규 발생 여부를 사용합니다.")
    else:
        contract_asset_growth = _growth_pct(contract_assets_t, contract_assets_prev)

    growth_gap = None
    if revenue_growth is not None and contract_asset_growth is not None:
        growth_gap = contract_asset_growth - revenue_growth

    ratio_t = _safe_div(contract_assets_t, revenue_t, 100) if revenue_t and revenue_t > 0 else None
    ratio_prev = _safe_div(contract_assets_prev, revenue_prev, 100) if revenue_prev and revenue_prev > 0 else None
    ratio_change = _pp_change(ratio_t, ratio_prev)
    if revenue_t is None or revenue_t <= 0:
        note_parts.append("당기 매출액이 없거나 0 이하라 계약자산/매출액 비율 계산이 제한됩니다.")

    ratio_3y_increase = False
    ratio_2023 = _safe_div(company_series[2023]["values"].get("계약자산"), company_series[2023]["values"].get("매출액"), 100)
    ratio_2024 = _safe_div(company_series[2024]["values"].get("계약자산"), company_series[2024]["values"].get("매출액"), 100)
    ratio_2025 = ratio_t
    if ratio_2023 is not None and ratio_2024 is not None and ratio_2025 is not None:
        ratio_3y_increase = ratio_2023 < ratio_2024 < ratio_2025

    risk_level = "정상"
    reason = "매출 증가 대비 계약자산 증가 부담이 현재 기준으로는 크지 않습니다."

    if revenue_t is None or revenue_prev is None or contract_assets_t is None or contract_assets_prev is None:
        if ratio_t is None and revenue_growth is None:
            risk_level = "판단불가"
            reason = "핵심 지표 계산에 필요한 매출액 또는 계약자산 데이터가 부족합니다."

    if risk_level != "판단불가":
        if ratio_3y_increase:
            risk_level = "고위험"
            reason = "계약자산/매출액 비율이 3년 연속 상승하여 고위험으로 분류했습니다."
        elif newly_generated and ratio_t is not None and ratio_t >= 5:
            risk_level = "고위험"
            reason = (
                f"전년도 계약자산이 0이었고 2025년 계약자산/매출액 비율이 {ratio_t:.1f}%로 5% 이상이어서 고위험으로 분류했습니다."
            )
        elif revenue_growth is not None and revenue_growth <= 0 and contract_asset_growth is not None and contract_asset_growth >= 30:
            risk_level = "고위험"
            reason = (
                f"매출액 증가율은 {revenue_growth:.1f}%인데 계약자산 증가율은 {contract_asset_growth:.1f}%로 높아 고위험으로 분류했습니다."
            )
        elif growth_gap is not None and growth_gap >= 50:
            risk_level = "위험"
            reason = (
                f"계약자산 증가율이 매출액 증가율을 {growth_gap:.1f}%p 초과하여 위험으로 분류했습니다."
            )
        elif ratio_change is not None and ratio_change >= 5:
            risk_level = "위험"
            reason = f"계약자산/매출액 비율이 전년 대비 {ratio_change:.1f}%p 상승하여 위험으로 분류했습니다."
        elif (
            revenue_growth is not None
            and contract_asset_growth is not None
            and revenue_growth > 0
            and contract_asset_growth >= revenue_growth * 2
            and ratio_change is not None
            and ratio_change >= 3
        ):
            risk_level = "위험"
            reason = "매출 성장 속도 대비 계약자산 증가 속도가 2배 이상이며 비율도 상승해 위험으로 분류했습니다."
        elif growth_gap is not None and ratio_change is not None and growth_gap >= 20 and ratio_change >= 3:
            risk_level = "주의"
            reason = (
                f"계약자산 증가율이 매출액 증가율을 {growth_gap:.1f}%p 초과하고 비율이 {ratio_change:.1f}%p 상승해 주의로 분류했습니다."
            )
        elif growth_gap is None and ratio_change is None:
            risk_level = "판단불가"
            reason = "증가율과 계약자산 비율을 모두 계산할 수 없어 판단불가로 분류했습니다."

    return {
        "revenue": revenue_t,
        "revenuePrev": revenue_prev,
        "contractAssets": contract_assets_t,
        "contractAssetsPrev": contract_assets_prev,
        "revenueGrowthPct": revenue_growth,
        "contractAssetsGrowthPct": contract_asset_growth,
        "growthGapPp": growth_gap,
        "contractAssetsToRevenuePct": ratio_t,
        "contractAssetsToRevenuePrevPct": ratio_prev,
        "contractAssetsRatioChangePp": ratio_change,
        "contractAssetsNewlyGeneratedFlag": newly_generated,
        "threeYearRatioIncreaseFlag": ratio_3y_increase,
        "riskLevel": risk_level,
        "riskReason": reason,
        "note": " ".join(note_parts) if note_parts else None,
    }


def get_anomaly_analysis(database_url: str, corp_code: str, group_scope: str) -> dict[str, Any]:
    if group_scope not in GROUP_SCOPES:
        raise ValueError("비교 그룹 범위가 올바르지 않습니다.")

    with _connect(database_url) as connection:
        company_levels = _fetch_company_levels(connection, "defense")
        if corp_code not in company_levels:
            raise LookupError("방산 분석 대상 기업이 아닙니다.")

        peer_codes = [code for code, level in company_levels.items() if level in GROUP_SCOPES[group_scope]]
        rows = _fetch_financial_rows(connection, "defense", [corp_code, *peer_codes], TARGET_ACCOUNTS)
        company_index = _build_company_year_index(rows)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT corp_code, stock_code, corp_name, market, memo
                FROM public.companies_basic
                WHERE corp_code = %(corp_code)s
                """,
                {"corp_code": corp_code},
            )
            company = cursor.fetchone()
            if company is None:
                raise LookupError("해당 기업정보가 존재하지 않습니다.")

    company_series = _series_for_company(company_index.get(corp_code, {}), TARGET_ACCOUNTS)
    current = company_series[CURRENT_YEAR]["values"]
    previous = company_series[CURRENT_YEAR - 1]["values"]

    operating_income_growth = _growth_pct(current.get("영업이익"), previous.get("영업이익"))
    cfo_growth = _growth_pct(current.get("영업활동현금흐름"), previous.get("영업활동현금흐름"))
    cfo_conversion = _safe_div(current.get("영업활동현금흐름"), current.get("영업이익"))
    contract_asset_ratio_2025 = _safe_div(current.get("계약자산"), current.get("매출액"), 100)
    contract_asset_ratio_2024 = _safe_div(previous.get("계약자산"), previous.get("매출액"), 100)

    contract_risk = _contract_asset_risk(company_series)

    signals = [
        {
            "code": "profit_up_cfo_down",
            "title": "영업이익 증가 + 영업활동현금흐름 감소",
            "triggered": (
                operating_income_growth is not None
                and cfo_growth is not None
                and operating_income_growth > 0
                and cfo_growth < 0
            ),
            "severity": "주의",
            "summary": (
                "영업이익은 증가했지만 영업활동현금흐름은 감소해 이익의 질 저하 가능성이 있습니다."
                if operating_income_growth is not None and cfo_growth is not None and operating_income_growth > 0 and cfo_growth < 0
                else "2025년 기준 영업이익 증가 + 영업활동현금흐름 감소 신호는 확인되지 않았습니다."
            ),
        },
        {
            "code": "negative_cfo_conversion",
            "title": "영업활동현금흐름 전환율 < 0",
            "triggered": cfo_conversion is not None and cfo_conversion < 0,
            "severity": "위험",
            "summary": (
                "회계상 이익과 현금흐름 간 괴리가 있어 현금화 리스크를 의심할 수 있습니다."
                if cfo_conversion is not None and cfo_conversion < 0
                else "영업활동현금흐름 전환율이 음수는 아닙니다."
            ),
        },
        {
            "code": "three_year_ratio_increase",
            "title": "계약자산 비율 3년 연속 상승",
            "triggered": contract_risk["threeYearRatioIncreaseFlag"],
            "severity": "고위험",
            "summary": (
                "계약자산/매출액 비율이 3년 연속 상승해 현금화 지연이 누적될 수 있습니다."
                if contract_risk["threeYearRatioIncreaseFlag"]
                else "최근 3년 기준 계약자산 비율의 연속 상승 신호는 없습니다."
            ),
        },
        {
            "code": "contract_asset_growth_gap",
            "title": "매출 증가율 대비 계약자산 증가율 과도 상승",
            "triggered": contract_risk["riskLevel"] in {"주의", "위험", "고위험"},
            "severity": contract_risk["riskLevel"],
            "summary": contract_risk["riskReason"],
        },
    ]

    indicators = [
        {
            "label": "영업이익 증가율",
            "value": operating_income_growth,
            "display": _format_percent(operating_income_growth),
            "description": "2025년 영업이익의 전년 대비 증가율",
        },
        {
            "label": "영업활동현금흐름 증가율",
            "value": cfo_growth,
            "display": _format_percent(cfo_growth),
            "description": "2025년 영업활동현금흐름의 전년 대비 증가율",
        },
        {
            "label": "영업활동현금흐름 전환율",
            "value": cfo_conversion,
            "display": _format_ratio(cfo_conversion),
            "description": "영업활동현금흐름 / 영업이익",
        },
        {
            "label": "계약자산/매출액 비율",
            "value": contract_asset_ratio_2025,
            "display": _format_percent(contract_asset_ratio_2025),
            "description": "2025년 계약자산 / 매출액",
        },
        {
            "label": "전년 대비 계약자산 비율 변화",
            "value": _pp_change(contract_asset_ratio_2025, contract_asset_ratio_2024),
            "display": _format_percent(_pp_change(contract_asset_ratio_2025, contract_asset_ratio_2024)),
            "description": "계약자산/매출액 비율의 %p 변화",
        },
    ]

    return {
        "company": dict(company),
        "year": CURRENT_YEAR,
        "groupScope": group_scope,
        "sourceBasis": company_series[CURRENT_YEAR]["basis"],
        "sourceLabel": company_series[CURRENT_YEAR]["source_label"],
        "overallRiskLevel": contract_risk["riskLevel"],
        "overallSummary": contract_risk["riskReason"],
        "note": contract_risk["note"],
        "indicators": indicators,
        "signals": signals,
        "contractAssetRisk": contract_risk,
    }
