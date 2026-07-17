"""Fill a specific missing account into a CSV bundle industry table using
rows already collected by `scripts/dart/main.py` into its SQLite dataset.

This is a narrow, auditable gap-fill step: it targets one canonical account
name at a time (e.g. "영업이익"), matches it against one or more raw DART
account_nm variants (DART's XBRL labels are not standardized across filers —
see the README data-contract notes), and only appends rows whose natural key
(corp_code, year, fs_div, sj_div, account_name) does not already exist in the
target CSV. It never overwrites or removes existing rows.

Typical flow:
    1. `diagnose_data_gaps.py` finds the missing cells and the required
       corp_code list for a given industry/account.
    2. `scripts/dart/main.py` fetches full financial statements for those
       corp_codes into a local SQLite dataset.
    3. This script extracts the one missing account from that dataset and
       appends it to the CSV bundle used by `upload_csv_bundle.py`.
    4. Re-run `upload_csv_bundle.py --validate-only` to confirm the merged
       bundle is still clean before uploading for real.

Example (construction 영업이익, missing for all 65 companies/3 years):
    backend/.venv/bin/python scripts/dart/fill_missing_accounts.py \
      --db-path /tmp/dart_construction/dart_dataset.db \
      --bundle-csv "look/Samil Project DB - construction.csv" \
      --account-variants "영업이익,영업이익(손실),IV.영업이익,IV. 영업이익" \
      --canonical-account "영업이익" \
      --sj-div "IS,CIS" \
      --memo "DART 재추출 2026-07-17"
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

INDUSTRY_TABLE_HEADERS = [
    "corp_code",
    "stock_code",
    "corp_name",
    "year",
    "fs_div",
    "sj_div",
    "account_name",
    "amount",
    "memo",
    "updated_at",
]


def load_existing_keys(bundle_csv: Path) -> set[tuple[str, str, str, str, str]]:
    keys: set[tuple[str, str, str, str, str]] = set()
    with bundle_csv.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            keys.add(
                (
                    row["corp_code"].strip(),
                    row["year"].strip(),
                    row["fs_div"].strip(),
                    row["sj_div"].strip(),
                    row["account_name"].strip(),
                )
            )
    return keys


def parse_amount(raw: str | None) -> int | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def extract_rows(
    db_path: Path,
    account_variants: list[str],
    sj_divs: list[str],
    canonical_account: str,
) -> list[dict[str, Any]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    placeholders_account = ",".join("?" for _ in account_variants)
    placeholders_sj = ",".join("?" for _ in sj_divs)
    cursor = connection.execute(
        f"""
        SELECT corp_code, stock_code, corp_name, bsns_year, fs_div, sj_div, account_nm, thstrm_amount
        FROM financial_statements
        WHERE account_nm IN ({placeholders_account})
          AND sj_div IN ({placeholders_sj})
        """,
        [*account_variants, *sj_divs],
    )
    raw_rows = cursor.fetchall()
    connection.close()

    # Guard against more than one matching account_nm variant landing on the same
    # (corp_code, year, fs_div): that would mean the variant list is too broad.
    grouped: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in raw_rows:
        grouped[(row["corp_code"], row["bsns_year"], row["fs_div"])].append(row)

    conflicts = {key: rows for key, rows in grouped.items() if len(rows) > 1}
    if conflicts:
        sample_key, sample_rows = next(iter(conflicts.items()))
        raise SystemExit(
            f"{len(conflicts)}개 (corp_code, year, fs_div) 조합에서 계정명 후보가 2개 이상 매칭됩니다. "
            f"--account-variants 범위를 좁혀주세요. 예: {sample_key} -> "
            f"{[r['account_nm'] for r in sample_rows]}"
        )

    today = date.today().isoformat()
    rows: list[dict[str, Any]] = []
    for (corp_code, year, fs_div), matches in grouped.items():
        source_row = matches[0]
        amount = parse_amount(source_row["thstrm_amount"])
        if amount is None:
            continue
        rows.append(
            {
                "corp_code": corp_code,
                "stock_code": source_row["stock_code"],
                "corp_name": source_row["corp_name"],
                "year": year,
                "fs_div": fs_div,
                "sj_div": source_row["sj_div"],
                "account_name": canonical_account,
                "amount": str(amount),
                "memo": "",
                "updated_at": today,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one DART-sourced account into a CSV bundle industry table.")
    parser.add_argument("--db-path", type=Path, required=True, help="SQLite dataset produced by scripts/dart/main.py.")
    parser.add_argument("--bundle-csv", type=Path, required=True, help="Target industry CSV file (e.g. look/*-construction.csv).")
    parser.add_argument("--account-variants", required=True, help="Comma-separated raw DART account_nm values to accept.")
    parser.add_argument("--canonical-account", required=True, help="Standard account_name to write (e.g. 영업이익).")
    parser.add_argument("--sj-div", default="IS,CIS", help="Comma-separated sj_div values to search within. Default: IS,CIS.")
    parser.add_argument("--memo", default="", help="Optional memo text to stamp on every appended row.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be appended without writing the CSV.")
    args = parser.parse_args()

    account_variants = [item.strip() for item in args.account_variants.split(",") if item.strip()]
    sj_divs = [item.strip() for item in args.sj_div.split(",") if item.strip()]

    existing_keys = load_existing_keys(args.bundle_csv)
    candidate_rows = extract_rows(args.db_path, account_variants, sj_divs, args.canonical_account)
    if args.memo:
        for row in candidate_rows:
            row["memo"] = args.memo

    new_rows = [
        row
        for row in candidate_rows
        if (row["corp_code"], row["year"], row["fs_div"], row["sj_div"], row["account_name"]) not in existing_keys
    ]
    skipped_existing = len(candidate_rows) - len(new_rows)

    print(f"DART에서 추출된 후보 행: {len(candidate_rows)}개")
    print(f"이미 번들에 있어 건너뜀: {skipped_existing}개")
    print(f"새로 추가할 행: {len(new_rows)}개")

    if args.dry_run or not new_rows:
        return

    existing_bytes = args.bundle_csv.read_bytes()
    needs_newline = bool(existing_bytes) and not existing_bytes.endswith((b"\n", b"\r"))

    with args.bundle_csv.open("a", encoding="utf-8-sig", newline="") as file:
        if needs_newline:
            file.write("\n")
        writer = csv.DictWriter(file, fieldnames=INDUSTRY_TABLE_HEADERS)
        for row in new_rows:
            writer.writerow(row)

    print(f"{args.bundle_csv}에 {len(new_rows)}개 행 추가 완료.")


if __name__ == "__main__":
    main()
