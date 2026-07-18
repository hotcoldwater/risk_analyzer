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


def clean_field(value: str) -> str:
    """Match the uploader's clean_identifier: strip spreadsheet-export quote
    artifacts (e.g. a cell literally containing 01199550") before comparing."""
    return (value or "").strip().strip('"').strip()


def normalize_corp_code(value: str) -> str:
    """Match the uploader's own zero-padding (clean_identifier(width=8)) so a
    padded "01524093" and an unpadded "1524093" in the bundle are recognized
    as the same natural key."""
    cleaned = clean_field(value)
    return cleaned.zfill(8) if cleaned.isdigit() else cleaned


def load_existing_keys(bundle_csv: Path) -> set[tuple[str, str, str, str, str]]:
    keys: set[tuple[str, str, str, str, str]] = set()
    with bundle_csv.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            keys.add(
                (
                    normalize_corp_code(row["corp_code"]),
                    clean_field(row["year"]),
                    clean_field(row["fs_div"]),
                    clean_field(row["sj_div"]),
                    clean_field(row["account_name"]),
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


def resolve_conflict(
    key: tuple[str, str, str],
    matches: list[sqlite3.Row],
    account_variants: list[str],
) -> sqlite3.Row:
    """Pick one row when several account_nm variants matched the same
    (corp_code, year, fs_div). Two resolvable patterns, both requiring an
    audit note:

    1. The *same* account_nm appears more than once (a filer split one line
       into a current/non-current breakdown under an identical label) — the
       row with the lowest statement `ord` (its position in the filing) is
       the one already used for companies that load cleanly today.
    2. *Different* account_nm variants matched — prefer whichever variant is
       listed first in --account-variants (the caller's priority order).

    Raises if neither rule narrows it to one row, so a genuinely ambiguous
    cell is never silently guessed.
    """
    distinct_names = {row["account_nm"] for row in matches}
    if len(distinct_names) == 1:
        try:
            chosen = min(matches, key=lambda row: int(row["ord"]))
        except (TypeError, ValueError):
            chosen = None
        if chosen is not None:
            print(f"  [해석] {key}: 동일 계정명 '{chosen['account_nm']}' 중복 -> ord={chosen['ord']}(최소) 채택")
            return chosen
    else:
        with_value = [row for row in matches if parse_amount(row["thstrm_amount"]) is not None]
        pool = with_value or matches
        for variant in account_variants:
            candidates = [row for row in pool if row["account_nm"] == variant]
            if candidates:
                chosen = candidates[0]
                other_names = sorted(distinct_names - {variant})
                reason = "값 없는 후보 제외 후 " if with_value != matches else ""
                print(f"  [해석] {key}: 후보 {other_names} 대신 {reason}우선순위가 높은 '{variant}' 채택")
                return chosen

    raise SystemExit(
        f"{key}에서 계정명 후보를 하나로 좁히지 못했습니다: "
        f"{[(r['account_nm'], r['ord'], r['thstrm_amount']) for r in matches]}. "
        "--account-variants 순서를 조정하거나 범위를 좁혀주세요."
    )


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
        SELECT corp_code, stock_code, corp_name, bsns_year, fs_div, sj_div, account_nm, ord, thstrm_amount
        FROM financial_statements
        WHERE account_nm IN ({placeholders_account})
          AND sj_div IN ({placeholders_sj})
        """,
        [*account_variants, *sj_divs],
    )
    raw_rows = cursor.fetchall()
    connection.close()

    grouped: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in raw_rows:
        grouped[(row["corp_code"], row["bsns_year"], row["fs_div"])].append(row)

    today = date.today().isoformat()
    rows: list[dict[str, Any]] = []
    for key, matches in grouped.items():
        source_row = matches[0] if len(matches) == 1 else resolve_conflict(key, matches, account_variants)
        corp_code, year, fs_div = key
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
        if (normalize_corp_code(row["corp_code"]), row["year"], row["fs_div"], row["sj_div"], row["account_name"]) not in existing_keys
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
