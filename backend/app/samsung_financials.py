from __future__ import annotations

from dataclasses import dataclass

from app.analyzer import calculate_debt_ratio
from app.dart_client import CorporationNotFoundError, find_corporation
from app.database import get_connection
from app.financial_extractor import extract_annual_financial_statements


SAMSUNG_ELECTRONICS_NAME = "삼성전자"
SAMSUNG_ELECTRONICS_STOCK_CODE = "005930"


@dataclass
class SyncResult:
    corp_name: str
    corp_code: str
    inserted: int
    updated: int
    total: int
    years: list[str]


def sync_samsung_financial_statements(years: int = 5) -> SyncResult:
    corporation_match = find_corporation(SAMSUNG_ELECTRONICS_STOCK_CODE)
    if corporation_match.corp.corp_name != SAMSUNG_ELECTRONICS_NAME:
        raise CorporationNotFoundError("삼성전자 기업 정보를 확인할 수 없습니다.")

    statements = extract_annual_financial_statements(corporation_match.corp, years=years)
    inserted = 0
    updated = 0

    with get_connection() as connection:
        for statement in statements:
            debt_ratio = calculate_debt_ratio(statement.liabilities, statement.equity)
            existing_row = connection.execute(
                """
                SELECT 1
                FROM financial_statements
                WHERE corp_code = ? AND business_year = ? AND statement_type = ?
                """,
                (corporation_match.corp.corp_code, statement.year, statement.statement_type),
            ).fetchone()

            connection.execute(
                """
                INSERT INTO financial_statements (
                    corp_code,
                    corp_name,
                    business_year,
                    statement_type,
                    liabilities,
                    equity,
                    debt_ratio,
                    unit,
                    liabilities_account_name,
                    equity_account_name,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(corp_code, business_year, statement_type)
                DO UPDATE SET
                    corp_name = excluded.corp_name,
                    liabilities = excluded.liabilities,
                    equity = excluded.equity,
                    debt_ratio = excluded.debt_ratio,
                    unit = excluded.unit,
                    liabilities_account_name = excluded.liabilities_account_name,
                    equity_account_name = excluded.equity_account_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    corporation_match.corp.corp_code,
                    corporation_match.corp.corp_name,
                    statement.year,
                    statement.statement_type,
                    statement.liabilities,
                    statement.equity,
                    debt_ratio,
                    statement.unit,
                    statement.liabilities_account_name,
                    statement.equity_account_name,
                ),
            )
            if existing_row is None:
                inserted += 1
            else:
                updated += 1

    years_synced = sorted({statement.year for statement in statements}, reverse=True)
    return SyncResult(
        corp_name=corporation_match.corp.corp_name,
        corp_code=corporation_match.corp.corp_code,
        inserted=inserted,
        updated=updated,
        total=len(statements),
        years=years_synced,
    )


def get_samsung_financial_statements() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                corp_name,
                corp_code,
                business_year,
                statement_type,
                liabilities,
                equity,
                debt_ratio,
                unit,
                liabilities_account_name,
                equity_account_name,
                updated_at
            FROM financial_statements
            WHERE corp_code = (
                SELECT corp_code
                FROM financial_statements
                WHERE corp_name = ?
                LIMIT 1
            )
            ORDER BY business_year DESC, statement_type ASC
            """,
            (SAMSUNG_ELECTRONICS_NAME,),
        ).fetchall()

    return [dict(row) for row in rows]
