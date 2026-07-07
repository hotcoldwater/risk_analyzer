from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "dart-data" / "db"
RAW_DB = DB_DIR / "dart_raw.db"
STANDARDS_DB = DB_DIR / "dart_standards.db"
SERVER_DB = DB_DIR / "dart_server.db"

SUPPORTED_STANDARD_ACCOUNTS = [
    "BS_ASSETS_TOTAL",
    "BS_LIABILITIES_TOTAL",
    "BS_EQUITY_TOTAL",
    "BS_CURRENT_ASSETS",
    "BS_CURRENT_LIABILITIES",
    "BS_RECEIVABLES",
    "BS_INVENTORIES",
    "BS_RETAINED_EARNINGS",
    "IS_REVENUE",
    "IS_GROSS_PROFIT",
    "IS_OPERATING_INCOME",
    "IS_NET_INCOME",
    "IS_FINANCE_COST",
    "CF_OPERATING",
]

SUPPORTED_ANALYSES = [
    {
        "analysis_code": "DEBT_RATIO",
        "analysis_name": "부채비율",
        "analysis_group": "basic_ratio",
        "required_accounts": "BS_LIABILITIES_TOTAL|BS_EQUITY_TOTAL",
        "status": "supported",
        "notes": "총부채/총자본 기반",
    },
    {
        "analysis_code": "OPERATING_MARGIN",
        "analysis_name": "영업이익률",
        "analysis_group": "basic_ratio",
        "required_accounts": "IS_OPERATING_INCOME|IS_REVENUE",
        "status": "supported",
        "notes": "영업이익/매출액",
    },
    {
        "analysis_code": "NET_MARGIN",
        "analysis_name": "순이익률",
        "analysis_group": "basic_ratio",
        "required_accounts": "IS_NET_INCOME|IS_REVENUE",
        "status": "supported",
        "notes": "당기순이익/매출액",
    },
    {
        "analysis_code": "GROSS_MARGIN",
        "analysis_name": "매출총이익률",
        "analysis_group": "basic_ratio",
        "required_accounts": "IS_GROSS_PROFIT|IS_REVENUE",
        "status": "supported",
        "notes": "매출총이익/매출액",
    },
    {
        "analysis_code": "INTEREST_COVERAGE",
        "analysis_name": "이자보상배율",
        "analysis_group": "basic_ratio",
        "required_accounts": "IS_OPERATING_INCOME|IS_FINANCE_COST",
        "status": "supported",
        "notes": "영업이익/금융비용",
    },
    {
        "analysis_code": "OCF_TO_NET_INCOME",
        "analysis_name": "영업활동현금흐름비율",
        "analysis_group": "basic_ratio",
        "required_accounts": "CF_OPERATING|IS_NET_INCOME",
        "status": "supported",
        "notes": "영업활동현금흐름/당기순이익",
    },
    {
        "analysis_code": "TREND_3Y",
        "analysis_name": "3개년 추세 분석",
        "analysis_group": "trend",
        "required_accounts": "BS_ASSETS_TOTAL|BS_LIABILITIES_TOTAL|BS_EQUITY_TOTAL|IS_REVENUE|IS_OPERATING_INCOME|IS_NET_INCOME|CF_OPERATING",
        "status": "supported",
        "notes": "2023~2025 시계열 기준",
    },
    {
        "analysis_code": "AR_VS_REVENUE",
        "analysis_name": "매출액 대비 매출채권 관계 분석",
        "analysis_group": "relationship",
        "required_accounts": "BS_RECEIVABLES|IS_REVENUE",
        "status": "supported",
        "notes": "매출 증가율과 매출채권 증가율 비교",
    },
    {
        "analysis_code": "INVENTORY_VS_REVENUE",
        "analysis_name": "매출액 대비 재고자산 관계 분석",
        "analysis_group": "relationship",
        "required_accounts": "BS_INVENTORIES|IS_REVENUE",
        "status": "supported",
        "notes": "매출 증가율과 재고 증가율 비교",
    },
    {
        "analysis_code": "NET_INCOME_VS_OCF",
        "analysis_name": "순이익 vs 영업활동현금흐름 괴리",
        "analysis_group": "relationship",
        "required_accounts": "IS_NET_INCOME|CF_OPERATING",
        "status": "supported",
        "notes": "이익의 질 분석",
    },
    {
        "analysis_code": "ANOMALY_RULES_MVP",
        "analysis_name": "이상징후 탐지 MVP",
        "analysis_group": "anomaly",
        "required_accounts": "BS_LIABILITIES_TOTAL|BS_EQUITY_TOTAL|BS_RECEIVABLES|BS_INVENTORIES|IS_REVENUE|IS_OPERATING_INCOME|IS_NET_INCOME|IS_FINANCE_COST|CF_OPERATING",
        "status": "supported",
        "notes": "AR_SPIKE, INV_SPIKE, OCF_NEGATIVE_WITH_PROFIT, OCF_LOW_QUALITY, DEBT_RATIO_SPIKE, OPERATING_MARGIN_DOWN, INTEREST_COVERAGE_LOW",
    },
    {
        "analysis_code": "ALTMAN_BOOK_PROXY",
        "analysis_name": "Altman Z-Score Book Value Proxy",
        "analysis_group": "model",
        "required_accounts": "BS_CURRENT_ASSETS|BS_CURRENT_LIABILITIES|BS_ASSETS_TOTAL|BS_RETAINED_EARNINGS|BS_LIABILITIES_TOTAL|BS_EQUITY_TOTAL|IS_REVENUE|IS_OPERATING_INCOME",
        "status": "supported",
        "notes": "시가총액 대신 장부가 자본 사용",
    },
]


def require_db(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"필수 DB가 없습니다: {path}")


def load_server_companies() -> pd.DataFrame:
    query = """
        SELECT
            corp_code AS company_id,
            corp_name AS company_name,
            stock_code,
            market,
            market_rank,
            market_cap_krw,
            current_price_krw,
            dart_sector_name,
            ksic_macro_sector
        FROM companies
    """
    with sqlite3.connect(RAW_DB) as connection:
        return pd.read_sql_query(query, connection)


def load_server_financials() -> pd.DataFrame:
    accounts_sql = ", ".join(f"'{account}'" for account in SUPPORTED_STANDARD_ACCOUNTS)
    query = f"""
        SELECT
            company_id,
            company_name,
            stock_code,
            year,
            fs_type,
            statement_type,
            standard_account_id,
            standard_account_nm,
            account_bucket,
            amount,
            source_row_count,
            source_account_names,
            source_account_ids,
            max_confidence,
            mapping_rules
        FROM standard_financials
        WHERE standard_account_id IN ({accounts_sql})
    """
    with sqlite3.connect(STANDARDS_DB) as connection:
        return pd.read_sql_query(query, connection)


def deduplicate_financials(financials: pd.DataFrame) -> pd.DataFrame:
    if financials.empty:
        return financials

    statement_priority = {
        "재무상태표": 1,
        "현금흐름표": 1,
        "손익계산서": 1,
        "포괄손익계산서": 2,
    }
    fs_priority = {
        "CFS": 1,
        "OFS": 2,
        "UNSPECIFIED": 3,
    }

    deduped = financials.copy()
    deduped["statement_priority"] = deduped["statement_type"].map(statement_priority).fillna(9)
    deduped["fs_priority"] = deduped["fs_type"].map(fs_priority).fillna(9)

    # Service DB expects one fact row per company-year-standard_account_id.
    # When IS and CIS expose the same metric, keep the higher-priority source.
    deduped = (
        deduped.sort_values(
            [
                "company_id",
                "year",
                "standard_account_id",
                "statement_priority",
                "fs_priority",
                "max_confidence",
                "source_row_count",
            ],
            ascending=[True, True, True, True, True, False, False],
        )
        .drop_duplicates(["company_id", "year", "standard_account_id"], keep="first")
        .drop(columns=["statement_priority", "fs_priority"])
        .reset_index(drop=True)
    )

    return deduped


def build_account_coverage(financials: pd.DataFrame) -> pd.DataFrame:
    return (
        financials.groupby(["standard_account_id", "standard_account_nm", "account_bucket"], dropna=False)
        .agg(
            rows=("company_id", "size"),
            companies=("company_id", "nunique"),
            min_year=("year", "min"),
            max_year=("year", "max"),
        )
        .reset_index()
        .sort_values(["companies", "rows", "standard_account_id"], ascending=[False, False, True])
    )


def build_supported_analyses() -> pd.DataFrame:
    return pd.DataFrame(SUPPORTED_ANALYSES)


def save_server_db(
    companies: pd.DataFrame,
    financials: pd.DataFrame,
    coverage: pd.DataFrame,
    analyses: pd.DataFrame,
) -> None:
    if SERVER_DB.exists():
        SERVER_DB.unlink()

    with sqlite3.connect(SERVER_DB) as connection:
        companies.to_sql("companies", connection, if_exists="replace", index=False)
        financials.to_sql("financials", connection, if_exists="replace", index=False)
        coverage.to_sql("account_coverage", connection, if_exists="replace", index=False)
        analyses.to_sql("supported_analyses", connection, if_exists="replace", index=False)

        connection.executescript(
            """
            CREATE INDEX idx_financials_company_year
            ON financials (company_id, year);

            CREATE INDEX idx_financials_account
            ON financials (standard_account_id, year);

            CREATE INDEX idx_companies_stock_code
            ON companies (stock_code);
            """
        )


def print_summary(
    companies: pd.DataFrame,
    financials: pd.DataFrame,
    coverage: pd.DataFrame,
    analyses: pd.DataFrame,
) -> None:
    print(f"회사 수: {len(companies):,}")
    print(f"재무 데이터 행 수: {len(financials):,}")
    print(f"지원 계정 수: {coverage['standard_account_id'].nunique():,}")
    print(f"지원 분석 수: {len(analyses):,}")
    print(f"연도 범위: {int(financials['year'].min())}~{int(financials['year'].max())}")


def main() -> None:
    require_db(RAW_DB)
    require_db(STANDARDS_DB)

    companies = load_server_companies()
    financials = deduplicate_financials(load_server_financials())
    coverage = build_account_coverage(financials)
    analyses = build_supported_analyses()

    save_server_db(companies, financials, coverage, analyses)
    print_summary(companies, financials, coverage, analyses)
    print(f"저장 완료: {SERVER_DB}")


if __name__ == "__main__":
    main()
