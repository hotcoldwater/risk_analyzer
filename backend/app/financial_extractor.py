from __future__ import annotations

from datetime import datetime
from typing import Iterable

from dart_fss.api.finance import fnltt_singl_acnt_all
from dart_fss.errors.errors import NoDataReceived

from app.normalizer import normalize_text, parse_amount
from app.schemas import ExtractionResult


LIABILITIES_CANDIDATES = (
    "부채총계",
    "총부채",
    "부채",
    "total liabilities",
    "liabilities",
)

EQUITY_CANDIDATES = (
    "자본총계",
    "총자본",
    "자본",
    "total equity",
    "equity",
    "total shareholders' equity",
)

STATEMENT_KEYWORDS = ("재무상태표", "statement of financial position", "balance sheet")


class FinancialDataError(ValueError):
    pass


def _fetch_statement_rows(corp_code: str, year: int, fs_div: str) -> list[dict]:
    try:
        payload = fnltt_singl_acnt_all(
            corp_code=corp_code,
            bsns_year=str(year),
            reprt_code="11011",
            fs_div=fs_div,
        )
    except NoDataReceived:
        return []
    except Exception as exc:
        raise FinancialDataError("DART 재무제표 조회에 실패했습니다.") from exc

    return payload.get("list", [])


def _row_matches_statement(row: dict) -> bool:
    subject = normalize_text(row.get("sj_nm") or row.get("sj_div") or "")
    return any(keyword in subject for keyword in STATEMENT_KEYWORDS)


def _select_account(rows: Iterable[dict], candidates: tuple[str, ...]) -> tuple[float, str]:
    for candidate in candidates:
        candidate_key = normalize_text(candidate)
        for row in rows:
            account_name = row.get("account_nm") or ""
            if normalize_text(account_name) == candidate_key:
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    return amount, account_name

    for candidate in candidates:
        candidate_key = normalize_text(candidate)
        for row in rows:
            account_name = row.get("account_nm") or ""
            if candidate_key in normalize_text(account_name):
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    return amount, account_name

    raise FinancialDataError(f"필요한 계정과목을 찾지 못했습니다: {', '.join(candidates)}")


def extract_latest_liabilities_and_equity(corp) -> ExtractionResult:
    current_year = datetime.now().year

    for year in range(current_year, current_year - 6, -1):
        for fs_div, statement_type in (("CFS", "연결재무제표"), ("OFS", "별도재무제표")):
            rows = _fetch_statement_rows(corp.corp_code, year, fs_div)
            statement_rows = [row for row in rows if _row_matches_statement(row)]
            if not statement_rows:
                continue

            liabilities, liabilities_account_name = _select_account(statement_rows, LIABILITIES_CANDIDATES)
            equity, equity_account_name = _select_account(statement_rows, EQUITY_CANDIDATES)

            return ExtractionResult(
                year=str(year),
                liabilities=liabilities,
                equity=equity,
                liabilitiesAccountName=liabilities_account_name,
                equityAccountName=equity_account_name,
                statementType=statement_type,
                unit="KRW",
            )

    raise FinancialDataError("해당 기업의 최신 재무제표 데이터를 찾을 수 없습니다.")


def extract_annual_financial_statements(corp, years: int = 5) -> list[ExtractionResult]:
    current_year = datetime.now().year
    results: list[ExtractionResult] = []

    for year in range(current_year, current_year - years, -1):
        for fs_div, statement_type in (("CFS", "연결재무제표"), ("OFS", "별도재무제표")):
            rows = _fetch_statement_rows(corp.corp_code, year, fs_div)
            statement_rows = [row for row in rows if _row_matches_statement(row)]
            if not statement_rows:
                continue

            liabilities, liabilities_account_name = _select_account(statement_rows, LIABILITIES_CANDIDATES)
            equity, equity_account_name = _select_account(statement_rows, EQUITY_CANDIDATES)

            results.append(
                ExtractionResult(
                    year=str(year),
                    liabilities=liabilities,
                    equity=equity,
                    liabilitiesAccountName=liabilities_account_name,
                    equityAccountName=equity_account_name,
                    statementType=statement_type,
                    unit="KRW",
                )
            )
            break

    if not results:
        raise FinancialDataError("해당 기업의 연도별 재무제표 데이터를 찾을 수 없습니다.")

    return results
