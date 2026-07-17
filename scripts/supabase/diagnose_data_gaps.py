"""Read-only diagnostic: find (corp_code, year, account_name) cells the risk
analysis needs but the DB does not have a usable value for, and classify why.

This is deliberately separate from `upload_csv_bundle.py` / `inspect_csv_bundle.py`:
those check a CSV bundle before it is loaded. This script checks the live
Supabase tables that the app actually queries today, so it reflects the real
gap the UI shows as "N/A" for a given industry's required accounts.

A missing cell here always means: DART re-extraction is a *candidate* fix.
It never means the app's CFS/OFS basis-selection is wrong — that is a
separate, non-DART issue (see README "다음 검증 지점"). This script counts a
cell as present as soon as it has a non-null amount under *either* fs_div,
which is the DB-completeness question, independent of which basis the app
later chooses to display.

Usage:
    backend/.venv/bin/python scripts/supabase/diagnose_data_gaps.py
    backend/.venv/bin/python scripts/supabase/diagnose_data_gaps.py --industry defense
    backend/.venv/bin/python scripts/supabase/diagnose_data_gaps.py --output gap_report.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_ENV = BACKEND_DIR / ".env"

sys.path.insert(0, str(BACKEND_DIR))

from app.defense_service import INDUSTRY_COMPARISON_ACCOUNTS  # noqa: E402

INDUSTRY_IDS = ["defense", "semiconductor", "construction"]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_database_url() -> str:
    load_env_file(BACKEND_ENV)
    database_url = os.getenv("SUPABASE_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is required. Set it in backend/.env or shell env.")
    return database_url


def diagnose_industry(connection: psycopg.Connection[Any], industry_id: str) -> list[dict[str, Any]]:
    accounts = INDUSTRY_COMPARISON_ACCOUNTS[industry_id]

    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT DISTINCT year FROM public.{} ORDER BY year").format(sql.Identifier(industry_id))
        )
        years = [row["year"] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT corp_code, corp_name, stock_code FROM public.industry_map WHERE industry_id = %(industry_id)s",
            {"industry_id": industry_id},
        )
        members = cursor.fetchall()

        cursor.execute(
            sql.SQL(
                "SELECT corp_code, year, fs_div, account_name, amount FROM public.{} WHERE account_name = ANY(%(accounts)s)"
            ).format(sql.Identifier(industry_id)),
            {"accounts": accounts},
        )
        rows = cursor.fetchall()

    # (corp_code, year, account_name) -> True if at least one fs_div row has a non-null amount
    has_value: dict[tuple[str, int, str], bool] = defaultdict(bool)
    has_any_row: dict[tuple[str, int, str], bool] = defaultdict(bool)
    for row in rows:
        key = (row["corp_code"], row["year"], row["account_name"])
        has_any_row[key] = True
        if row["amount"] is not None:
            has_value[key] = True

    gaps: list[dict[str, Any]] = []
    for member in members:
        for year in years:
            for account in accounts:
                key = (member["corp_code"], year, account)
                if has_value.get(key):
                    continue
                gap_type = "null_amount" if has_any_row.get(key) else "source_gap"
                gaps.append(
                    {
                        "industry_id": industry_id,
                        "corp_code": member["corp_code"],
                        "corp_name": member["corp_name"],
                        "stock_code": member["stock_code"],
                        "year": year,
                        "account_name": account,
                        "gap_type": gap_type,
                    }
                )
    return gaps


def summarize(gaps: list[dict[str, Any]]) -> dict[str, Any]:
    by_industry: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_company: dict[tuple[str, str], int] = defaultdict(int)
    for gap in gaps:
        by_industry[gap["industry_id"]][gap["gap_type"]] += 1
        by_company[(gap["industry_id"], gap["corp_code"], gap["corp_name"])] += 1  # type: ignore[index]

    worst_companies = sorted(
        ({"industry_id": k[0], "corp_code": k[1], "corp_name": k[2], "gap_count": v} for k, v in by_company.items()),
        key=lambda item: item["gap_count"],
        reverse=True,
    )[:15]

    return {
        "total_gaps": len(gaps),
        "by_industry": {industry: dict(counts) for industry, counts in by_industry.items()},
        "worst_companies": worst_companies,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose missing/null financial-fact cells in the live DB.")
    parser.add_argument("--industry", choices=INDUSTRY_IDS, help="Limit to a single industry (default: all three).")
    parser.add_argument("--output", type=Path, help="Write the full gap list as CSV to this path.")
    args = parser.parse_args()

    database_url = get_database_url()
    industries = [args.industry] if args.industry else INDUSTRY_IDS

    all_gaps: list[dict[str, Any]] = []
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        for industry_id in industries:
            all_gaps.extend(diagnose_industry(connection, industry_id))

    summary = summarize(all_gaps)
    print(f"총 결측 셀: {summary['total_gaps']}개\n")
    for industry_id, counts in summary["by_industry"].items():
        source_gap = counts.get("source_gap", 0)
        null_amount = counts.get("null_amount", 0)
        print(f"[{industry_id}] source_gap(행 자체 없음)={source_gap}  null_amount(행은 있으나 값 없음)={null_amount}")

    if summary["worst_companies"]:
        print("\n결측이 가장 많은 기업 (상위 15개):")
        for item in summary["worst_companies"]:
            print(f"  {item['industry_id']:14s} {item['corp_name']:20s} ({item['corp_code']})  결측 {item['gap_count']}건")

    if args.output:
        with args.output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["industry_id", "corp_code", "corp_name", "stock_code", "year", "account_name", "gap_type"],
            )
            writer.writeheader()
            writer.writerows(all_gaps)
        print(f"\n전체 결측 목록 CSV 저장: {args.output}")


if __name__ == "__main__":
    main()
