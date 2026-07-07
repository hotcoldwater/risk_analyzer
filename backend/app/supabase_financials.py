from __future__ import annotations

from dataclasses import dataclass

from psycopg.rows import dict_row
import psycopg


@dataclass(frozen=True)
class SupabaseDebtRatioResult:
    company_id: str
    company_name: str
    year: str
    liabilities: float
    equity: float
    source: str = "Supabase"


def _normalize_query(query: str) -> str:
    return query.strip()


def fetch_latest_debt_ratio_data(database_url: str, query: str) -> SupabaseDebtRatioResult:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        raise ValueError("기업명 또는 기업번호를 입력해 주세요.")

    sql = """
        WITH matched_companies AS (
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
        ),
        latest_year AS (
            SELECT
                f.company_id,
                MAX(f.year) AS year
            FROM public.financials f
            JOIN matched_companies mc ON mc.company_id = f.company_id
            WHERE f.standard_account_id IN ('BS_LIABILITIES_TOTAL', 'BS_EQUITY_TOTAL')
            GROUP BY f.company_id
        ),
        pivoted AS (
            SELECT
                mc.company_id,
                mc.company_name,
                ly.year,
                MAX(CASE WHEN f.standard_account_id = 'BS_LIABILITIES_TOTAL' THEN f.amount END) AS liabilities,
                MAX(CASE WHEN f.standard_account_id = 'BS_EQUITY_TOTAL' THEN f.amount END) AS equity,
                mc.match_rank
            FROM matched_companies mc
            JOIN latest_year ly ON ly.company_id = mc.company_id
            JOIN public.financials f
              ON f.company_id = ly.company_id
             AND f.year = ly.year
             AND f.standard_account_id IN ('BS_LIABILITIES_TOTAL', 'BS_EQUITY_TOTAL')
            GROUP BY mc.company_id, mc.company_name, ly.year, mc.match_rank
        )
        SELECT
            company_id,
            company_name,
            year::text AS year,
            liabilities,
            equity
        FROM pivoted
        WHERE liabilities IS NOT NULL AND equity IS NOT NULL
        ORDER BY match_rank, year DESC, company_name
        LIMIT 1
    """

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "query": normalized_query,
                    "query_like": f"%{normalized_query}%",
                },
            )
            row = cursor.fetchone()

    if row is None:
        raise LookupError("Supabase에 해당 기업의 서비스용 재무데이터가 없습니다.")

    return SupabaseDebtRatioResult(
        company_id=row["company_id"],
        company_name=row["company_name"],
        year=row["year"],
        liabilities=float(row["liabilities"]),
        equity=float(row["equity"]),
    )
