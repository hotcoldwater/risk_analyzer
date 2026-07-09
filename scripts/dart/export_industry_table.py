from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


DEFAULT_DB_PATH = Path("data/workspace/dart/dart_dataset.db")
DEFAULT_CORP_CODES_PATH = Path("data/input/dart/corp_codes.txt")
DEFAULT_INDUSTRY_MAP_PATH = Path("/Users/da_vid/Downloads/Samil Project DB - industry_map.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/industry_tables")
DEFAULT_YEARS = ["2025", "2024", "2023", "2022", "2021"]

TARGET_ACCOUNTS = [
    "매출액",
    "영업이익",
    "영업활동현금흐름",
    "계약자산",
    "계약부채",
    "매출채권",
    "재고자산",
]


@dataclass(frozen=True)
class CompanyKey:
    corp_code: str
    stock_code: str
    corp_name: str


@dataclass
class MatchResult:
    fs_div: str
    sj_div: str
    amount: int
    source_accounts: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export normalized industry table rows from the DART workspace DB.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--corp-codes-file", type=Path, default=DEFAULT_CORP_CODES_PATH)
    parser.add_argument("--industry-map-path", type=Path, default=DEFAULT_INDUSTRY_MAP_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table-name", default="industry_table")
    return parser.parse_args()


def load_corp_codes(path: Path) -> list[str]:
    corp_codes: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        corp_code = "".join(ch for ch in stripped if ch.isdigit())
        if len(corp_code) != 8 or corp_code in seen:
            continue
        seen.add(corp_code)
        corp_codes.append(corp_code)
    return corp_codes


def load_levels(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    levels: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            corp_code = (row.get("corp_code") or "").strip()
            if corp_code:
                levels[corp_code] = (row.get("level") or "").strip()
    return levels


def normalize_text(value: str | None) -> str:
    return (value or "").replace(" ", "").strip()


def classify_account(metric: str, row: sqlite3.Row) -> bool:
    account_id = row["account_id"] or ""
    account_name = row["account_nm"] or ""
    account_name_normalized = normalize_text(account_name)
    sj_div = row["sj_div"] or ""

    if metric == "매출액":
        return sj_div in {"IS", "CIS"} and account_id == "ifrs-full_Revenue"
    if metric == "영업이익":
        return sj_div in {"IS", "CIS"} and account_id == "dart_OperatingIncomeLoss"
    if metric == "영업활동현금흐름":
        return sj_div == "CF" and account_id == "ifrs-full_CashFlowsFromUsedInOperatingActivities"
    if metric == "계약자산":
        return sj_div == "BS" and (
            "ContractAsset" in account_id
            or account_name_normalized
            in {
                "계약자산",
                "유동계약자산",
                "장기계약자산",
                "비유동계약자산",
                "계약자산(미청구공사수익)",
                "확정계약자산",
                "유동확정계약자산",
                "비유동확정계약자산",
                "미청구공사",
            }
        )
    if metric == "계약부채":
        return sj_div == "BS" and (
            "ContractLiabilit" in account_id
            or account_name_normalized
            in {
                "계약부채",
                "유동계약부채",
                "장기계약부채",
                "비유동계약부채",
                "계약부채(초과청구공사)",
                "계약부채(초과청구공사수익)",
                "확정계약부채",
                "유동확정계약부채",
                "비유동확정계약부채",
                "장기성계약부채",
                "초과청구공사",
                "이연수익",
                "유동성이연수익",
            }
        )
    if metric == "매출채권":
        return sj_div == "BS" and (
            "Receivable" in account_id
            or account_name_normalized
            in {
                "매출채권",
                "단기매출채권",
                "유동매출채권",
                "장기매출채권",
                "비유동매출채권",
                "장기성매출채권",
                "매출채권및기타유동채권",
                "매출채권및기타채권",
                "매출채권및기타비유동채권",
                "매출채권및상각후원가측정금융자산",
                "장기매출채권및기타채권",
                "장기매출채권및기타비유동채권",
                "장기매출채권및기타비유동채권,총액",
                "비유동매출채권및기타채권",
            }
        )
    if metric == "재고자산":
        return sj_div == "BS" and (
            account_id in {"ifrs-full_Inventories", "ifrs-full_InventoriesTotal"}
            or account_name_normalized in {"재고자산", "유동재고자산"}
        )
    return False


def related_account(metric: str, row: sqlite3.Row) -> bool:
    account_name = row["account_nm"] or ""
    account_name_normalized = normalize_text(account_name)
    sj_div = row["sj_div"] or ""

    if metric in {"매출액", "영업이익"}:
        return sj_div in {"IS", "CIS"} and (
            "매출" in account_name or "영업수익" in account_name or "영업이익" in account_name or "영업손익" in account_name
        )
    if metric == "영업활동현금흐름":
        return sj_div == "CF" and "영업활동" in account_name
    if metric == "계약자산":
        return sj_div == "BS" and (
            "계약" in account_name or "미청구" in account_name_normalized
        )
    if metric == "계약부채":
        return sj_div == "BS" and (
            "계약" in account_name or "초과청구" in account_name_normalized or "이연수익" in account_name_normalized
        )
    if metric == "매출채권":
        return sj_div == "BS" and "매출채권" in account_name
    if metric == "재고자산":
        return sj_div == "BS" and "재고자산" in account_name
    return False


def choose_amount(rows: list[sqlite3.Row]) -> MatchResult:
    fs_div = rows[0]["fs_div"] or ""
    sj_div = rows[0]["sj_div"] or ""
    amount = 0
    source_accounts: list[str] = []
    for row in rows:
        raw_amount = row["thstrm_amount"] or ""
        if raw_amount:
            try:
                amount += int(raw_amount)
            except ValueError:
                pass
        account_name = row["account_nm"] or ""
        if account_name and account_name not in source_accounts:
            source_accounts.append(account_name)
    return MatchResult(fs_div=fs_div, sj_div=sj_div, amount=amount, source_accounts=source_accounts)


def build_rows(
    conn: sqlite3.Connection,
    corp_codes: list[str],
    levels: dict[str, str],
) -> list[list[str]]:
    company_rows = conn.execute(
        """
        SELECT corp_code, stock_code, corp_name
        FROM companies
        WHERE corp_code IN ({})
        ORDER BY corp_name
        """.format(",".join("?" for _ in corp_codes)),
        corp_codes,
    ).fetchall()
    preferred_rows = conn.execute(
        """
        SELECT corp_code, stock_code, corp_name, bsns_year, fs_div, sj_div, account_id, account_nm, thstrm_amount
        FROM preferred_financial_statements
        WHERE corp_code IN ({}) AND bsns_year IN ('2025','2024','2023','2022','2021')
        """.format(",".join("?" for _ in corp_codes)),
        corp_codes,
    ).fetchall()

    rows_by_company_year: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    available_years: dict[str, set[str]] = defaultdict(set)
    for row in preferred_rows:
        rows_by_company_year[(row["corp_code"], row["bsns_year"])].append(row)
        available_years[row["corp_code"]].add(row["bsns_year"])

    header_rows: list[list[str]] = []
    updated_at = date.today().isoformat()

    for company_row in company_rows:
        company = CompanyKey(
            corp_code=company_row["corp_code"],
            stock_code=company_row["stock_code"],
            corp_name=company_row["corp_name"],
        )
        for year in DEFAULT_YEARS:
            year_rows = rows_by_company_year.get((company.corp_code, year), [])
            for metric in TARGET_ACCOUNTS:
                matched_rows = [row for row in year_rows if classify_account(metric, row)]
                memo = ""
                fs_div = ""
                sj_div = ""
                amount = ""

                if matched_rows:
                    chosen = choose_amount(matched_rows)
                    fs_div = chosen.fs_div
                    sj_div = chosen.sj_div
                    amount = str(chosen.amount)
                    normalized_sources = sorted(set(chosen.source_accounts))
                    if normalized_sources != [metric]:
                        if len(normalized_sources) == 1:
                            memo = f"원천계정명: {normalized_sources[0]}"
                        else:
                            memo = f"합산 원천계정: {'|'.join(normalized_sources)}"
                else:
                    if not year_rows:
                        available = "|".join(sorted(available_years.get(company.corp_code, set())))
                        memo = f"해당 연도 원천 재무제표 없음"
                        if available:
                            memo += f" (보유연도: {available})"
                    else:
                        related_rows = [row for row in year_rows if related_account(metric, row)]
                        if related_rows:
                            related_names: list[str] = []
                            for row in related_rows:
                                account_name = row["account_nm"] or ""
                                if account_name and account_name not in related_names:
                                    related_names.append(account_name)
                            memo = f"표준 매칭 없음, 유사계정: {'|'.join(related_names[:6])}"
                        else:
                            memo = "해당 연도 재무제표에 해당 계정 없음"

                header_rows.append(
                    [
                        company.corp_code,
                        company.stock_code,
                        company.corp_name,
                        year,
                        fs_div,
                        sj_div,
                        metric,
                        amount,
                        memo,
                        updated_at,
                    ]
                )

    return header_rows


def write_outputs(output_dir: Path, table_name: str, rows: list[list[str]]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tsv_path = output_dir / f"{table_name}.tsv"
    csv_path = output_dir / f"{table_name}.csv"
    header = ["corp_code", "stock_code", "corp_name", "year", "fs_div", "sj_div", "account_name", "amount", "memo", "updated_at"]

    for path, dialect in ((tsv_path, "excel-tab"), (csv_path, "excel")):
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, dialect=dialect)
            writer.writerow(header)
            writer.writerows(rows)

    return tsv_path, csv_path


def main() -> int:
    args = parse_args()
    corp_codes = load_corp_codes(args.corp_codes_file)
    levels = load_levels(args.industry_map_path)
    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = build_rows(conn, corp_codes, levels)
    finally:
        conn.close()

    tsv_path, csv_path = write_outputs(args.output_dir, args.table_name, rows)
    print(tsv_path)
    print(csv_path)
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
