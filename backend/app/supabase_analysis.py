from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class CompanyMatch:
    company_id: str
    company_name: str
    stock_code: str | None


@dataclass(frozen=True)
class CompanySearchResult:
    company_id: str
    company_name: str
    stock_code: str | None
    market: str | None
    market_rank: int | None
    market_cap_krw: int | None


@dataclass(frozen=True)
class CompanyOverview:
    company_id: str
    company_name: str
    stock_code: str | None
    market: str | None
    market_rank: int | None
    market_cap_krw: int | None
    current_price_krw: int | None
    series: list[dict[str, float | str | None]]


@dataclass(frozen=True)
class AnalysisDefinitionRecord:
    analysis_code: str
    analysis_name: str
    analysis_group: str
    notes: str | None


@dataclass(frozen=True)
class AnalysisResult:
    company_id: str
    company_name: str
    stock_code: str | None
    analysis_code: str
    analysis_name: str
    analysis_group: str
    year: str
    summary: str
    available_years: list[str]
    metrics: list[dict[str, str]]
    highlights: list[str]
    warnings: list[str]
    source: str = "Supabase"


FinancialIndex = dict[int, dict[str, float]]

IMPLEMENTED_ANALYSIS_CODES = [
    "DEBT_RATIO",
    "OPERATING_MARGIN",
    "NET_MARGIN",
    "GROSS_MARGIN",
    "INTEREST_COVERAGE",
    "OCF_TO_NET_INCOME",
    "TREND_3Y",
    "AR_VS_REVENUE",
    "INVENTORY_VS_REVENUE",
    "NET_INCOME_VS_OCF",
    "ANOMALY_RULES_MVP",
    "ALTMAN_BOOK_PROXY",
]


def _safe_ratio(numerator: float | None, denominator: float | None, multiplier: float = 1.0) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * multiplier


def _format_number(value: float | None, suffix: str = "", decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}{suffix}"


def _format_currency(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.0f}원"


def _latest_year(financials: FinancialIndex) -> int:
    if not financials:
        raise LookupError("Supabase에 해당 기업의 분석용 재무데이터가 없습니다.")
    return max(financials)


def _previous_year(financials: FinancialIndex, year: int) -> int | None:
    previous = sorted(candidate for candidate in financials if candidate < year)
    return previous[-1] if previous else None


def _latest_value(financials: FinancialIndex, year: int | None, account_id: str) -> float | None:
    if year is None:
        return None
    return financials.get(year, {}).get(account_id)


def _change_rate(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def _debt_ratio(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "BS_LIABILITIES_TOTAL"), _latest_value(financials, year, "BS_EQUITY_TOTAL"), 100)


def _operating_margin(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "IS_OPERATING_INCOME"), _latest_value(financials, year, "IS_REVENUE"), 100)


def _net_margin(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "IS_NET_INCOME"), _latest_value(financials, year, "IS_REVENUE"), 100)


def _gross_margin(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "IS_GROSS_PROFIT"), _latest_value(financials, year, "IS_REVENUE"), 100)


def _interest_coverage(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "IS_OPERATING_INCOME"), _latest_value(financials, year, "IS_FINANCE_COST"))


def _ocf_to_net_income(financials: FinancialIndex, year: int | None) -> float | None:
    return _safe_ratio(_latest_value(financials, year, "CF_OPERATING"), _latest_value(financials, year, "IS_NET_INCOME"))


def _available_years(financials: FinancialIndex) -> list[str]:
    return [str(year) for year in sorted(financials)]


def _build_result(
    company: CompanyMatch,
    definition: AnalysisDefinitionRecord,
    year: int,
    summary: str,
    metrics: list[dict[str, str]],
    highlights: list[str],
    warnings: list[str],
    financials: FinancialIndex,
) -> AnalysisResult:
    return AnalysisResult(
        company_id=company.company_id,
        company_name=company.company_name,
        stock_code=company.stock_code,
        analysis_code=definition.analysis_code,
        analysis_name=definition.analysis_name,
        analysis_group=definition.analysis_group,
        year=str(year),
        summary=summary,
        available_years=_available_years(financials),
        metrics=metrics,
        highlights=highlights,
        warnings=warnings,
    )


def _analyze_debt_ratio(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    ratio = _debt_ratio(financials, year)
    prev_year = _previous_year(financials, year)
    prev_ratio = _debt_ratio(financials, prev_year)
    ratio_change = ratio - prev_ratio if ratio is not None and prev_ratio is not None else None
    warnings = []
    if ratio is not None and ratio >= 200:
        warnings.append("부채비율이 200% 이상입니다.")
    if ratio_change is not None and ratio_change >= 30:
        warnings.append("전년 대비 부채비율이 30%p 이상 상승했습니다.")
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 부채비율은 {_format_number(ratio, '%')}입니다.",
        [
            {"label": "부채비율", "value": _format_number(ratio, "%"), "tone": "primary"},
            {"label": "총부채", "value": _format_currency(_latest_value(financials, year, 'BS_LIABILITIES_TOTAL'))},
            {"label": "총자본", "value": _format_currency(_latest_value(financials, year, 'BS_EQUITY_TOTAL'))},
            {"label": "전년 대비 변화", "value": _format_number(ratio_change, "%p") if ratio_change is not None else "N/A"},
        ],
        ["부채비율 = 총부채 / 총자본 × 100"],
        warnings,
        financials,
    )


def _analyze_margin(
    company: CompanyMatch,
    definition: AnalysisDefinitionRecord,
    financials: FinancialIndex,
    ratio_func: Callable[[FinancialIndex, int | None], float | None],
    ratio_label: str,
    profit_account: str,
) -> AnalysisResult:
    year = _latest_year(financials)
    ratio = ratio_func(financials, year)
    prev_year = _previous_year(financials, year)
    prev_ratio = ratio_func(financials, prev_year)
    ratio_change = ratio - prev_ratio if ratio is not None and prev_ratio is not None else None
    warnings = [f"{ratio_label}이 음수입니다."] if ratio is not None and ratio < 0 else []
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 {ratio_label}은 {_format_number(ratio, '%')}입니다.",
        [
            {"label": ratio_label, "value": _format_number(ratio, "%"), "tone": "primary"},
            {"label": "매출액", "value": _format_currency(_latest_value(financials, year, 'IS_REVENUE'))},
            {"label": "관련 이익", "value": _format_currency(_latest_value(financials, year, profit_account))},
            {"label": "전년 대비 변화", "value": _format_number(ratio_change, "%p") if ratio_change is not None else "N/A"},
        ],
        ["최근 3개년 데이터 중 최신 연도를 기준으로 계산했습니다."],
        warnings,
        financials,
    )


def _analyze_interest_coverage(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    ratio = _interest_coverage(financials, year)
    warnings = ["이자보상배율이 1 미만입니다."] if ratio is not None and ratio < 1 else []
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 이자보상배율은 {_format_number(ratio)}배입니다.",
        [
            {"label": "이자보상배율", "value": _format_number(ratio), "tone": "primary"},
            {"label": "영업이익", "value": _format_currency(_latest_value(financials, year, 'IS_OPERATING_INCOME'))},
            {"label": "금융비용", "value": _format_currency(_latest_value(financials, year, 'IS_FINANCE_COST'))},
        ],
        ["이자보상배율 = 영업이익 / 금융비용"],
        warnings,
        financials,
    )


def _analyze_ocf_ratio(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    ratio = _ocf_to_net_income(financials, year)
    warnings = ["영업활동현금흐름비율이 0.5 미만입니다."] if ratio is not None and ratio < 0.5 else []
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 영업활동현금흐름비율은 {_format_number(ratio)}배입니다.",
        [
            {"label": "영업활동현금흐름비율", "value": _format_number(ratio), "tone": "primary"},
            {"label": "영업활동현금흐름", "value": _format_currency(_latest_value(financials, year, 'CF_OPERATING'))},
            {"label": "당기순이익", "value": _format_currency(_latest_value(financials, year, 'IS_NET_INCOME'))},
        ],
        ["영업활동현금흐름비율 = 영업활동현금흐름 / 당기순이익"],
        warnings,
        financials,
    )


def _relationship_analysis(
    company: CompanyMatch,
    definition: AnalysisDefinitionRecord,
    financials: FinancialIndex,
    account_id: str,
    account_label: str,
) -> AnalysisResult:
    year = _latest_year(financials)
    prev_year = _previous_year(financials, year)
    revenue_current = _latest_value(financials, year, "IS_REVENUE")
    revenue_prev = _latest_value(financials, prev_year, "IS_REVENUE")
    account_current = _latest_value(financials, year, account_id)
    account_prev = _latest_value(financials, prev_year, account_id)
    revenue_change = _change_rate(revenue_current, revenue_prev)
    account_change = _change_rate(account_current, account_prev)
    delta_gap = account_change - revenue_change if revenue_change is not None and account_change is not None else None
    warnings = []
    if delta_gap is not None and delta_gap > 20:
        warnings.append(f"{account_label} 증가율이 매출 증가율보다 20%p 이상 높습니다.")
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 매출 증가율은 {_format_number(revenue_change, '%')}이고, {account_label} 증가율은 {_format_number(account_change, '%')}입니다.",
        [
            {"label": "매출 증가율", "value": _format_number(revenue_change, "%"), "tone": "primary"},
            {"label": f"{account_label} 증가율", "value": _format_number(account_change, "%"), "tone": "primary"},
            {"label": "증가율 격차", "value": _format_number(delta_gap, "%p") if delta_gap is not None else "N/A"},
            {"label": f"{account_label}/매출액", "value": _format_number(_safe_ratio(account_current, revenue_current, 100), "%")},
        ],
        [f"{account_label} 증가율 > 매출 증가율 + 20%p 여부를 점검합니다."],
        warnings,
        financials,
    )


def _net_income_vs_ocf(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    net_income = _latest_value(financials, year, "IS_NET_INCOME")
    ocf = _latest_value(financials, year, "CF_OPERATING")
    ratio = _ocf_to_net_income(financials, year)
    gap = net_income - ocf if net_income is not None and ocf is not None else None
    warnings = []
    if net_income is not None and net_income > 0 and ocf is not None and ocf < 0:
        warnings.append("당기순이익은 흑자이나 영업활동현금흐름은 적자입니다.")
    if ratio is not None and ratio < 0.5:
        warnings.append("영업활동현금흐름이 순이익 대비 낮습니다.")
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 당기순이익과 영업활동현금흐름의 차이는 {_format_currency(gap)}입니다.",
        [
            {"label": "당기순이익", "value": _format_currency(net_income), "tone": "primary"},
            {"label": "영업활동현금흐름", "value": _format_currency(ocf), "tone": "primary"},
            {"label": "영업활동현금흐름비율", "value": _format_number(ratio)},
            {"label": "차이", "value": _format_currency(gap)},
        ],
        ["순이익과 현금흐름의 괴리를 통해 이익의 질을 확인합니다."],
        warnings,
        financials,
    )


def _trend_3y(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    years = sorted(financials)
    year = years[-1]
    prev_year = years[-2] if len(years) >= 2 else None
    revenue_change = _change_rate(_latest_value(financials, year, "IS_REVENUE"), _latest_value(financials, prev_year, "IS_REVENUE"))
    operating_change = _change_rate(_latest_value(financials, year, "IS_OPERATING_INCOME"), _latest_value(financials, prev_year, "IS_OPERATING_INCOME"))
    net_change = _change_rate(_latest_value(financials, year, "IS_NET_INCOME"), _latest_value(financials, prev_year, "IS_NET_INCOME"))
    debt_current = _debt_ratio(financials, year)
    debt_prev = _debt_ratio(financials, prev_year)
    debt_change = debt_current - debt_prev if debt_current is not None and debt_prev is not None else None
    return _build_result(
        company,
        definition,
        year,
        f"최근 3개년({years[0]}~{years[-1]}) 기준 주요 계정과 부채비율 추세를 요약했습니다.",
        [
            {"label": "매출 증가율", "value": _format_number(revenue_change, "%"), "tone": "primary"},
            {"label": "영업이익 증가율", "value": _format_number(operating_change, "%")},
            {"label": "순이익 증가율", "value": _format_number(net_change, "%")},
            {"label": "부채비율 변화", "value": _format_number(debt_change, "%p") if debt_change is not None else "N/A"},
        ],
        ["현재 서비스용 데이터는 2023~2025 최근 3개년을 기준으로 합니다."],
        [],
        financials,
    )


def _anomaly_rules_mvp(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    prev_year = _previous_year(financials, year)
    signals: list[str] = []
    debt_ratio = _debt_ratio(financials, year)
    prev_debt_ratio = _debt_ratio(financials, prev_year)
    if debt_ratio is not None and debt_ratio >= 200:
        signals.append("부채비율 200% 이상")
    if debt_ratio is not None and prev_debt_ratio is not None and debt_ratio - prev_debt_ratio >= 30:
        signals.append("부채비율 전년 대비 30%p 이상 상승")
    op_margin = _operating_margin(financials, year)
    if prev_year is not None:
        older_year = _previous_year(financials, prev_year)
        prev_margin = _operating_margin(financials, prev_year)
        older_margin = _operating_margin(financials, older_year)
        if op_margin is not None and prev_margin is not None and older_margin is not None and op_margin < prev_margin < older_margin:
            signals.append("영업이익률 2년 연속 하락")
    interest_coverage = _interest_coverage(financials, year)
    if interest_coverage is not None and interest_coverage < 1:
        signals.append("이자보상배율 1 미만")
    net_income = _latest_value(financials, year, "IS_NET_INCOME")
    ocf = _latest_value(financials, year, "CF_OPERATING")
    if net_income is not None and net_income > 0 and ocf is not None and ocf < 0:
        signals.append("흑자이나 영업활동현금흐름 적자")
    ocf_ratio = _ocf_to_net_income(financials, year)
    if ocf_ratio is not None and ocf_ratio < 0.5:
        signals.append("영업활동현금흐름 / 순이익 < 0.5")

    def relationship_signal(account_id: str, label: str) -> None:
        current = _latest_value(financials, year, account_id)
        previous = _latest_value(financials, prev_year, account_id)
        revenue_current = _latest_value(financials, year, "IS_REVENUE")
        revenue_previous = _latest_value(financials, prev_year, "IS_REVENUE")
        current_change = _change_rate(current, previous)
        revenue_change = _change_rate(revenue_current, revenue_previous)
        if current_change is not None and revenue_change is not None and current_change > revenue_change + 20:
            signals.append(f"{label} 증가율이 매출 증가율보다 20%p 이상 높음")

    if prev_year is not None:
        relationship_signal("BS_RECEIVABLES", "매출채권")
        relationship_signal("BS_INVENTORIES", "재고자산")

    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 MVP 이상징후 {len(signals)}건을 탐지했습니다.",
        [
            {"label": "탐지 건수", "value": str(len(signals)), "tone": "primary"},
            {"label": "부채비율", "value": _format_number(debt_ratio, "%")},
            {"label": "영업이익률", "value": _format_number(op_margin, "%")},
            {"label": "이자보상배율", "value": _format_number(interest_coverage)},
        ],
        ["현재 서비스는 핵심 이상징후만 우선 탐지합니다."],
        signals or ["탐지된 주요 이상징후가 없습니다."],
        financials,
    )


def _altman_book_proxy(company: CompanyMatch, definition: AnalysisDefinitionRecord, financials: FinancialIndex) -> AnalysisResult:
    year = _latest_year(financials)
    total_assets = _latest_value(financials, year, "BS_ASSETS_TOTAL")
    current_assets = _latest_value(financials, year, "BS_CURRENT_ASSETS")
    current_liabilities = _latest_value(financials, year, "BS_CURRENT_LIABILITIES")
    retained_earnings = _latest_value(financials, year, "BS_RETAINED_EARNINGS")
    operating_income = _latest_value(financials, year, "IS_OPERATING_INCOME")
    equity = _latest_value(financials, year, "BS_EQUITY_TOTAL")
    liabilities = _latest_value(financials, year, "BS_LIABILITIES_TOTAL")
    revenue = _latest_value(financials, year, "IS_REVENUE")
    x1 = _safe_ratio((current_assets or 0) - (current_liabilities or 0), total_assets)
    x2 = _safe_ratio(retained_earnings, total_assets)
    x3 = _safe_ratio(operating_income, total_assets)
    x4 = _safe_ratio(equity, liabilities)
    x5 = _safe_ratio(revenue, total_assets)
    values = [x1, x2, x3, x4, x5]
    z_score = None if any(value is None for value in values) else 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    warnings = []
    if z_score is not None:
        if z_score < 1.81:
            warnings.append("부실위험 높음 구간입니다.")
        elif z_score <= 2.99:
            warnings.append("회색지대 구간입니다.")
    return _build_result(
        company,
        definition,
        year,
        f"{year}년 기준 Altman Z-Score Book Value Proxy는 {_format_number(z_score)}입니다.",
        [
            {"label": "Z-Score", "value": _format_number(z_score), "tone": "primary"},
            {"label": "X1", "value": _format_number(x1)},
            {"label": "X2", "value": _format_number(x2)},
            {"label": "X3", "value": _format_number(x3)},
            {"label": "X4", "value": _format_number(x4)},
            {"label": "X5", "value": _format_number(x5)},
        ],
        ["시가총액 대신 장부가 자본을 사용하는 프록시 모델입니다."],
        warnings,
        financials,
    )


ANALYSIS_HANDLERS: dict[str, Callable[[CompanyMatch, AnalysisDefinitionRecord, FinancialIndex], AnalysisResult]] = {
    "DEBT_RATIO": _analyze_debt_ratio,
    "OPERATING_MARGIN": lambda c, d, f: _analyze_margin(c, d, f, _operating_margin, "영업이익률", "IS_OPERATING_INCOME"),
    "NET_MARGIN": lambda c, d, f: _analyze_margin(c, d, f, _net_margin, "순이익률", "IS_NET_INCOME"),
    "GROSS_MARGIN": lambda c, d, f: _analyze_margin(c, d, f, _gross_margin, "매출총이익률", "IS_GROSS_PROFIT"),
    "INTEREST_COVERAGE": _analyze_interest_coverage,
    "OCF_TO_NET_INCOME": _analyze_ocf_ratio,
    "TREND_3Y": _trend_3y,
    "AR_VS_REVENUE": lambda c, d, f: _relationship_analysis(c, d, f, "BS_RECEIVABLES", "매출채권"),
    "INVENTORY_VS_REVENUE": lambda c, d, f: _relationship_analysis(c, d, f, "BS_INVENTORIES", "재고자산"),
    "NET_INCOME_VS_OCF": _net_income_vs_ocf,
    "ANOMALY_RULES_MVP": _anomaly_rules_mvp,
    "ALTMAN_BOOK_PROXY": _altman_book_proxy,
}


def _fetch_company_match(connection: psycopg.Connection, query: str) -> CompanyMatch:
    sql = """
        SELECT company_id, company_name, stock_code
        FROM (
            SELECT
                company_id,
                company_name,
                stock_code,
                CASE
                    WHEN company_id = %(query)s THEN 1
                    WHEN stock_code = %(query)s THEN 2
                    WHEN company_name = %(query)s THEN 3
                    WHEN company_name ILIKE %(query_like)s THEN 4
                    ELSE 5
                END AS match_rank
            FROM public.companies
            WHERE company_id = %(query)s
               OR stock_code = %(query)s
               OR company_name = %(query)s
               OR company_name ILIKE %(query_like)s
        ) matched
        ORDER BY match_rank, company_name
        LIMIT 1
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {"query": query, "query_like": f"%{query}%"})
        row = cursor.fetchone()
    if row is None:
        raise LookupError("Supabase에 해당 기업의 서비스용 재무데이터가 없습니다.")
    return CompanyMatch(row["company_id"], row["company_name"], row["stock_code"])


def _fetch_company_by_id(connection: psycopg.Connection, company_id: str) -> CompanySearchResult:
    sql = """
        SELECT company_id, company_name, stock_code, market, market_rank, market_cap_krw
        FROM public.companies
        WHERE company_id = %(company_id)s
        LIMIT 1
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {"company_id": company_id})
        row = cursor.fetchone()
    if row is None:
        raise LookupError("기업 정보를 찾지 못했습니다.")
    return CompanySearchResult(
        row["company_id"],
        row["company_name"],
        row["stock_code"],
        row["market"],
        row["market_rank"],
        row["market_cap_krw"],
    )


def _fetch_financial_index(connection: psycopg.Connection, company_id: str) -> FinancialIndex:
    sql = """
        SELECT year, standard_account_id, amount
        FROM public.financials
        WHERE company_id = %(company_id)s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {"company_id": company_id})
        rows = cursor.fetchall()
    financials: FinancialIndex = {}
    for row in rows:
        year = int(row["year"])
        financials.setdefault(year, {})[row["standard_account_id"]] = float(row["amount"])
    return financials


def search_companies(database_url: str, query: str, limit: int = 12) -> list[CompanySearchResult]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    sql = """
        SELECT company_id, company_name, stock_code, market, market_rank, market_cap_krw
        FROM (
            SELECT
                company_id,
                company_name,
                stock_code,
                market,
                market_rank,
                market_cap_krw,
                CASE
                    WHEN company_name ILIKE %(starts_with)s THEN 1
                    WHEN stock_code ILIKE %(starts_with)s THEN 2
                    WHEN company_name ILIKE %(contains)s THEN 3
                    WHEN stock_code ILIKE %(contains)s THEN 4
                    ELSE 5
                END AS match_rank
            FROM public.companies
            WHERE company_name ILIKE %(contains)s
               OR stock_code ILIKE %(contains)s
        ) matched
        ORDER BY match_rank, market_cap_krw DESC NULLS LAST, company_name
        LIMIT %(limit)s
    """
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "starts_with": f"{normalized_query}%",
                    "contains": f"%{normalized_query}%",
                    "limit": limit,
                },
            )
            rows = cursor.fetchall()
    return [
        CompanySearchResult(
            row["company_id"],
            row["company_name"],
            row["stock_code"],
            row["market"],
            row["market_rank"],
            row["market_cap_krw"],
        )
        for row in rows
    ]


def fetch_company_overview(database_url: str, company_id: str) -> CompanyOverview:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        company = _fetch_company_by_id(connection, company_id)
        financials = _fetch_financial_index(connection, company_id)

        price_sql = """
            SELECT current_price_krw
            FROM public.companies
            WHERE company_id = %(company_id)s
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(price_sql, {"company_id": company_id})
            price_row = cursor.fetchone()

    years = sorted(financials)
    series = [
        {
            "year": str(year),
            "revenue": _latest_value(financials, year, "IS_REVENUE"),
            "grossProfit": _latest_value(financials, year, "IS_GROSS_PROFIT"),
            "operatingIncome": _latest_value(financials, year, "IS_OPERATING_INCOME"),
            "netIncome": _latest_value(financials, year, "IS_NET_INCOME"),
        }
        for year in years
    ]

    return CompanyOverview(
        company.company_id,
        company.company_name,
        company.stock_code,
        company.market,
        company.market_rank,
        company.market_cap_krw,
        price_row["current_price_krw"] if price_row else None,
        series,
    )


def fetch_supported_analyses(database_url: str) -> list[AnalysisDefinitionRecord]:
    sql = """
        SELECT analysis_code, analysis_name, analysis_group, notes
        FROM public.supported_analyses
        WHERE analysis_code = ANY(%(codes)s)
        ORDER BY analysis_name
    """
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"codes": IMPLEMENTED_ANALYSIS_CODES})
            rows = cursor.fetchall()
    return [AnalysisDefinitionRecord(row["analysis_code"], row["analysis_name"], row["analysis_group"], row["notes"]) for row in rows]


def run_analysis(database_url: str, query: str, analysis_code: str) -> AnalysisResult:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("기업명 또는 기업번호를 입력해 주세요.")
    if analysis_code not in ANALYSIS_HANDLERS:
        raise ValueError("지원하지 않는 분석 코드입니다.")

    definitions = {definition.analysis_code: definition for definition in fetch_supported_analyses(database_url)}
    definition = definitions.get(analysis_code)
    if definition is None:
        raise LookupError("지원 분석 정의를 찾지 못했습니다.")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        company = _fetch_company_match(connection, normalized_query)
        financials = _fetch_financial_index(connection, company.company_id)

    return ANALYSIS_HANDLERS[analysis_code](company, definition, financials)
