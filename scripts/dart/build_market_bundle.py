"""One-time bootstrap for the KOSPI/KOSDAQ market-wide expansion (Phase 5,
see README "코스피·코스닥 전체 시장 확장").

Given a market universe CSV (market, stock_code, corp_name, corp_code,
market_rank — see scripts/dart/main.py's MarketCapSelector + DART corp_code
master matching) and each market's DART SQLite dataset (from
scripts/dart/main.py), this:

1. Appends any company not already in companies_basic.csv (dedup by corp_code
   — most of the 144 companies from the 3 curated industries are also
   KOSPI/KOSDAQ listed and must not be duplicated).
2. Appends a kospi/kosdaq industry_map membership row for every company in
   the universe, including ones that already have a defense/semiconductor/
   construction membership (industry_map supports multi-membership by design).
3. Creates an empty, header-only kospi.csv / kosdaq.csv per market so that
   `fill_missing_accounts.py` can be run in a loop (once per standard
   account) to populate it exactly like the existing industries.

This script never touches the per-industry fact CSVs (defense/semiconductor/
construction) and never removes existing companies_basic/industry_map rows.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

COMPANIES_BASIC_HEADERS = [
    "corp_code", "stock_code", "corp_name", "market", "ksic_code", "ksic_name",
    "memo", "updated_at", "수익인식기준", "수익인식 코드", "분류",
]
INDUSTRY_MAP_HEADERS = [
    "corp_code", "stock_code", "corp_name", "industry_id", "is_primary",
    "level", "level_category", "memo", "updated_at",
]
INDUSTRY_TABLE_HEADERS = [
    "corp_code", "stock_code", "corp_name", "year", "fs_div", "sj_div",
    "account_name", "amount", "memo", "updated_at",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_dart_companies(db_path: Path) -> dict[str, dict[str, str]]:
    import sqlite3

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT corp_code, stock_code, corp_name, dart_sector_name, ksic_macro_sector FROM companies"
    ).fetchall()
    connection.close()
    return {row["corp_code"]: dict(row) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap companies_basic/industry_map/fact-table CSVs for a market-wide industry.")
    parser.add_argument("--universe-csv", type=Path, required=True, help="market,stock_code,corp_name,corp_code,market_rank")
    parser.add_argument("--market", required=True, choices=["KOSPI", "KOSDAQ"])
    parser.add_argument("--industry-id", required=True, help="e.g. kospi or kosdaq")
    parser.add_argument("--dart-db", type=Path, required=True, help="SQLite dataset from scripts/dart/main.py for this market")
    parser.add_argument("--companies-basic-csv", type=Path, required=True)
    parser.add_argument("--industry-map-csv", type=Path, required=True)
    parser.add_argument("--fact-table-csv", type=Path, required=True, help="Output path, e.g. look/Samil Project DB - kospi.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    universe = [row for row in read_rows(args.universe_csv) if row["market"] == args.market]
    dart_companies = read_dart_companies(args.dart_db)

    existing_basic_rows = read_rows(args.companies_basic_csv)
    existing_basic_codes = {row["corp_code"].strip().strip('"').zfill(8) for row in existing_basic_rows}

    existing_map_rows = read_rows(args.industry_map_csv)
    existing_map_keys = {(row["corp_code"].strip(), row["industry_id"].strip()) for row in existing_map_rows}

    today = date.today().isoformat()
    new_basic_rows: list[dict[str, str]] = []
    new_map_rows: list[dict[str, str]] = []
    skipped_basic = 0
    skipped_map = 0

    for entry in universe:
        corp_code = entry["corp_code"].strip()
        dart_info = dart_companies.get(corp_code, {})
        corp_name = dart_info.get("corp_name") or entry["corp_name"]

        if corp_code not in existing_basic_codes:
            new_basic_rows.append(
                {
                    "corp_code": corp_code,
                    "stock_code": entry["stock_code"],
                    "corp_name": corp_name,
                    "market": args.market,
                    "ksic_code": dart_info.get("dart_sector_name") or "",
                    "ksic_name": dart_info.get("ksic_macro_sector") or "",
                    "memo": "",
                    "updated_at": today,
                    "수익인식기준": "",
                    "수익인식 코드": "",
                    "분류": "",
                }
            )
            existing_basic_codes.add(corp_code)
        else:
            skipped_basic += 1

        map_key = (corp_code, args.industry_id)
        if map_key not in existing_map_keys:
            new_map_rows.append(
                {
                    "corp_code": corp_code,
                    "stock_code": entry["stock_code"],
                    "corp_name": corp_name,
                    "industry_id": args.industry_id,
                    "is_primary": "FALSE",
                    "level": "UNCLASSIFIED",
                    "level_category": "",
                    "memo": f"{args.market} 시장 전체 편입",
                    "updated_at": today,
                }
            )
            existing_map_keys.add(map_key)
        else:
            skipped_map += 1

    print(f"companies_basic: 신규 {len(new_basic_rows)}개, 기존 보유로 건너뜀 {skipped_basic}개")
    print(f"industry_map: 신규 {len(new_map_rows)}개, 기존 보유로 건너뜀 {skipped_map}개")
    print(f"fact table 헤더만 생성: {args.fact_table_csv}")

    if args.dry_run:
        return

    with args.companies_basic_csv.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPANIES_BASIC_HEADERS)
        for row in new_basic_rows:
            writer.writerow(row)

    with args.industry_map_csv.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDUSTRY_MAP_HEADERS)
        for row in new_map_rows:
            writer.writerow(row)

    with args.fact_table_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDUSTRY_TABLE_HEADERS)
        writer.writeheader()

    print("완료.")


if __name__ == "__main__":
    main()
