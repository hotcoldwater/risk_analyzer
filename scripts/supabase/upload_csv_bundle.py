from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "upload"
BACKEND_ENV = PROJECT_ROOT / "backend" / ".env"

COMPANIES_BASIC_HEADERS = [
    "corp_code",
    "stock_code",
    "corp_name",
    "market",
    "ksic_code",
    "ksic_name",
    "memo",
    "updated_at",
]

# The first eight fields are the backwards-compatible company master contract.
# These fields were added to the July 2026 bundle and are intentionally optional
# while old upload/ bundles are still supported.
COMPANIES_BASIC_OPTIONAL_HEADERS = [
    "수익인식기준",
    "수익인식 코드",
    "분류",
]
COMPANIES_BASIC_ALL_HEADERS = COMPANIES_BASIC_HEADERS + COMPANIES_BASIC_OPTIONAL_HEADERS

INDUSTRY_MAP_HEADERS = [
    "corp_code",
    "stock_code",
    "corp_name",
    "industry_id",
    "is_primary",
    "level",
    "level_category",
    "memo",
    "updated_at",
]

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

KNOWN_LEGACY_TABLES = [
    "companies",
    "financials",
    "account_coverage",
    "supported_analyses",
    "companies_basic",
    "industry_map",
]


@dataclass
class CsvBundle:
    companies_basic_path: Path
    industry_map_path: Path
    industry_table_paths: dict[str, Path]


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


def normalize_table_name(path: Path) -> str:
    stem = path.stem
    if " - " in stem:
        stem = stem.split(" - ", 1)[1]
    return stem.strip().lower().replace(" ", "_").replace("-", "_")


def discover_bundle(upload_dir: Path) -> CsvBundle:
    csv_paths = sorted(path for path in upload_dir.glob("*.csv") if path.is_file())
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in {upload_dir}")

    table_map = {normalize_table_name(path): path for path in csv_paths}
    missing = [name for name in ("companies_basic", "industry_map") if name not in table_map]
    if missing:
        raise FileNotFoundError(f"Missing required CSV files: {', '.join(missing)}")

    industry_table_paths = {
        table_name: path
        for table_name, path in table_map.items()
        if table_name not in {"companies_basic", "industry_map"}
    }
    return CsvBundle(
        companies_basic_path=table_map["companies_basic"],
        industry_map_path=table_map["industry_map"],
        industry_table_paths=industry_table_paths,
    )


def parse_date(value: str, field_name: str, row_number: int, path: Path) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{path.name}:{row_number} invalid {field_name} date: {value}") from error


def parse_bool(value: str, field_name: str, row_number: int, path: Path) -> bool:
    normalized = value.strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise ValueError(f"{path.name}:{row_number} invalid {field_name} boolean: {value}")


def clean_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def clean_identifier(value: str, width: int | None = None) -> str:
    """Remove spreadsheet-export quoting without changing meaningful content."""
    cleaned = value.strip().strip('"').strip()
    if width and cleaned.isdigit():
        return cleaned.zfill(width)
    return cleaned


def parse_amount(value: str, row_number: int, path: Path) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    normalized = stripped.replace(",", "").replace(" ", "")
    if not normalized or normalized in {"-", "+"}:
        raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    if not amount.is_finite():
        raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    return amount


def validate_headers(path: Path, expected_headers: list[str]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"{path.name} is empty") from error
    if headers != expected_headers:
        raise ValueError(f"{path.name} header mismatch: expected={expected_headers}, actual={headers}")


def validate_companies_basic_headers(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"{path.name} is empty") from error
    if tuple(headers) not in {tuple(COMPANIES_BASIC_HEADERS), tuple(COMPANIES_BASIC_ALL_HEADERS)}:
        raise ValueError(
            f"{path.name} header mismatch: expected={COMPANIES_BASIC_HEADERS} "
            f"or {COMPANIES_BASIC_ALL_HEADERS}, actual={headers}"
        )
    return headers


def normalize_industry_headers(path: Path) -> None:
    """Accept the legacy blank memo/updated_at headers only when both are blank.

    The actual row positions still have to match the standard 10-field contract;
    this makes the accepted cleanup explicit and avoids treating arbitrary headers
    as valid financial data.
    """
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"{path.name} is empty") from error
    if headers == INDUSTRY_TABLE_HEADERS:
        return
    if headers == INDUSTRY_TABLE_HEADERS[:8] + ["", ""]:
        return
    raise ValueError(f"{path.name} header mismatch: expected={INDUSTRY_TABLE_HEADERS}, actual={headers}")


def load_companies_basic(
    path: Path,
    default_updated_at: date | None = None,
) -> tuple[list[tuple[Any, ...]], dict[str, dict[str, str]]]:
    headers = validate_companies_basic_headers(path)
    rows: list[tuple[Any, ...]] = []
    master: dict[str, dict[str, str]] = {}

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            corp_code = clean_identifier(row["corp_code"], width=8)
            stock_code = clean_identifier(row["stock_code"], width=6)
            corp_name = row["corp_name"].strip()

            if not (corp_code.isdigit() and len(corp_code) == 8):
                raise ValueError(f"{path.name}:{row_number} invalid corp_code: {corp_code}")
            if not (stock_code.isalnum() and len(stock_code) == 6):
                raise ValueError(f"{path.name}:{row_number} invalid stock_code: {stock_code}")
            if not corp_name:
                raise ValueError(f"{path.name}:{row_number} corp_name is required")
            if corp_code in master:
                raise ValueError(f"{path.name}:{row_number} duplicated corp_code: {corp_code}")

            updated_at_raw = row["updated_at"].strip()
            if updated_at_raw:
                updated_at = parse_date(updated_at_raw, "updated_at", row_number, path)
            elif default_updated_at is not None:
                updated_at = default_updated_at
            else:
                raise ValueError(
                    f"{path.name}:{row_number} missing updated_at. "
                    "Pass --default-updated-at only for an approved bundle-wide default."
                )
            master[corp_code] = {
                "corp_code": corp_code,
                "stock_code": stock_code,
                "corp_name": corp_name,
            }
            revenue_recognition_basis = clean_text(row.get("수익인식기준", "")) if headers else None
            revenue_recognition_code = clean_text(row.get("수익인식 코드", "")) if headers else None
            classification = clean_text(row.get("분류", "")) if headers else None
            rows.append(
                (
                    corp_code,
                    stock_code,
                    corp_name,
                    clean_text(row["market"]),
                    clean_text(row["ksic_code"]),
                    clean_text(row["ksic_name"]),
                    clean_text(row["memo"]),
                    updated_at,
                    revenue_recognition_basis,
                    revenue_recognition_code,
                    classification,
                )
            )

    return rows, master


def canonicalize_company(
    *,
    path: Path,
    row_number: int,
    master: dict[str, dict[str, str]],
    corp_code: str,
    stock_code: str,
    corp_name: str,
) -> str:
    company = master.get(corp_code)
    if company is None:
        raise ValueError(f"{path.name}:{row_number} corp_code not found in companies_basic: {corp_code}")
    if company["stock_code"] != stock_code:
        raise ValueError(
            f"{path.name}:{row_number} stock_code mismatch for {corp_code}: {stock_code} != {company['stock_code']}"
        )
    return company["corp_name"]


def load_industry_map(
    path: Path,
    master: dict[str, dict[str, str]],
    reconcile_stock_codes: bool = False,
) -> list[tuple[Any, ...]]:
    validate_headers(path, INDUSTRY_MAP_HEADERS)
    rows: list[tuple[Any, ...]] = []
    seen_keys: set[tuple[str, str]] = set()

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            corp_code = clean_identifier(row["corp_code"], width=8)
            stock_code = clean_identifier(row["stock_code"], width=6)
            corp_name = row["corp_name"].strip()
            industry_id = row["industry_id"].strip()

            if reconcile_stock_codes and corp_code in master:
                stock_code = master[corp_code]["stock_code"]

            canonical_name = canonicalize_company(
                path=path,
                row_number=row_number,
                master=master,
                corp_code=corp_code,
                stock_code=stock_code,
                corp_name=corp_name,
            )

            if not industry_id:
                raise ValueError(f"{path.name}:{row_number} industry_id is required")

            key = (industry_id, corp_code)
            if key in seen_keys:
                raise ValueError(f"{path.name}:{row_number} duplicated industry mapping: {industry_id}/{corp_code}")
            seen_keys.add(key)

            rows.append(
                (
                    corp_code,
                    stock_code,
                    canonical_name,
                    industry_id,
                    parse_bool(row["is_primary"], "is_primary", row_number, path),
                    clean_text(row["level"]),
                    clean_text(row["level_category"]),
                    clean_text(row["memo"]),
                    parse_date(row["updated_at"].strip(), "updated_at", row_number, path),
                )
            )

    return rows


def load_industry_table(
    path: Path,
    master: dict[str, dict[str, str]],
    default_updated_at: date | None = None,
) -> list[tuple[Any, ...]]:
    normalize_industry_headers(path)
    rows: list[tuple[Any, ...]] = []

    with path.open(encoding="utf-8-sig", newline="") as file:
        raw_reader = csv.reader(file)
        headers = next(raw_reader)
        # Two blank headers are a known spreadsheet export defect in the latest
        # semiconductor bundle. Rebind their positions to the canonical names
        # before interpreting the remaining rows.
        normalized_headers = INDUSTRY_TABLE_HEADERS if headers[-2:] == ["", ""] else headers
        reader = (dict(zip(normalized_headers, values, strict=True)) for values in raw_reader)
        for row_number, row in enumerate(reader, start=2):
            corp_code = clean_identifier(row["corp_code"], width=8)
            stock_code = clean_identifier(row["stock_code"], width=6)
            corp_name = row["corp_name"].strip()

            if not (corp_code.isdigit() and len(corp_code) == 8):
                raise ValueError(f"{path.name}:{row_number} invalid corp_code: {corp_code}")
            if not (stock_code.isalnum() and len(stock_code) == 6):
                raise ValueError(f"{path.name}:{row_number} invalid stock_code: {stock_code}")
            if not corp_name:
                raise ValueError(f"{path.name}:{row_number} corp_name is required")

            canonical_name = canonicalize_company(
                path=path,
                row_number=row_number,
                master=master,
                corp_code=corp_code,
                stock_code=stock_code,
                corp_name=corp_name,
            )

            year_raw = row["year"].strip()
            if not year_raw.isdigit():
                raise ValueError(f"{path.name}:{row_number} invalid year: {year_raw}")

            account_name = row["account_name"].strip()
            if not account_name:
                raise ValueError(f"{path.name}:{row_number} account_name is required")

            rows.append(
                (
                    corp_code,
                    stock_code,
                    canonical_name,
                    int(year_raw),
                    clean_text(row["fs_div"]),
                    clean_text(row["sj_div"]),
                    account_name,
                    parse_amount(row["amount"], row_number, path),
                    clean_text(row["memo"]),
                    (
                        parse_date(row["updated_at"].strip(), "updated_at", row_number, path)
                        if row["updated_at"].strip()
                        else default_updated_at
                    ),
                )
            )

            if rows[-1][-1] is None:
                raise ValueError(
                    f"{path.name}:{row_number} missing updated_at. "
                    "Pass --default-updated-at only for an approved bundle-wide default."
                )

    duplicate_keys: set[tuple[str, int, str | None, str | None, str]] = set()
    for corp_code, _, _, year, fs_div, sj_div, account_name, *_ in rows:
        key = (corp_code, year, fs_div, sj_div, account_name)
        if key in duplicate_keys:
            raise ValueError(
                f"{path.name} duplicated financial fact: corp_code={corp_code}, year={year}, "
                f"fs_div={fs_div}, sj_div={sj_div}, account_name={account_name}"
            )
        duplicate_keys.add(key)
    return rows


def discover_consistent_financial_stock_codes(paths: dict[str, Path]) -> dict[str, tuple[str, str]]:
    """Return a financial-file stock code only when every row agrees."""
    observed: dict[str, set[tuple[str, str]]] = {}
    for path in paths.values():
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            if headers is None:
                continue
            normalized_headers = INDUSTRY_TABLE_HEADERS if headers[-2:] == ["", ""] else headers
            if normalized_headers != INDUSTRY_TABLE_HEADERS:
                continue
            for values in reader:
                row = dict(zip(normalized_headers, values, strict=True))
                corp_code = clean_identifier(row["corp_code"], width=8)
                stock_code = clean_identifier(row["stock_code"], width=6)
                corp_name = row["corp_name"].strip()
                if corp_code and stock_code and corp_name:
                    observed.setdefault(corp_code, set()).add((stock_code, corp_name))
    return {corp_code: next(iter(values)) for corp_code, values in observed.items() if len(values) == 1}


def reconcile_master_stock_codes(
    *,
    companies_rows: list[tuple[Any, ...]],
    master: dict[str, dict[str, str]],
    industry_table_paths: dict[str, Path],
) -> tuple[list[tuple[Any, ...]], list[tuple[str, str, str, str]]]:
    """Repair a stale master code only when the corporation name also agrees."""
    financial_codes = discover_consistent_financial_stock_codes(industry_table_paths)
    corrections: list[tuple[str, str, str, str]] = []
    replacements: dict[str, str] = {}
    for corp_code, company in master.items():
        financial_record = financial_codes.get(corp_code)
        if financial_record is None:
            continue
        financial_stock_code, financial_name = financial_record
        if company["corp_name"] != financial_name or company["stock_code"] == financial_stock_code:
            continue
        corrections.append((corp_code, company["corp_name"], company["stock_code"], financial_stock_code))
        replacements[corp_code] = financial_stock_code
        company["stock_code"] = financial_stock_code
    corrected_rows = [(row[0], replacements.get(row[0], row[1]), *row[2:]) for row in companies_rows]
    return corrected_rows, corrections


def create_companies_basic_table(connection: psycopg.Connection[Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE public.companies_basic (
                corp_code TEXT PRIMARY KEY,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                market TEXT,
                ksic_code TEXT,
                ksic_name TEXT,
                memo TEXT,
                updated_at DATE NOT NULL,
                revenue_recognition_basis TEXT,
                revenue_recognition_code TEXT,
                classification TEXT
            )
            """
        )
        cursor.execute("CREATE INDEX companies_basic_corp_name_idx ON public.companies_basic (corp_name)")


def create_industry_map_table(connection: psycopg.Connection[Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE public.industry_map (
                corp_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                industry_id TEXT NOT NULL,
                is_primary BOOLEAN NOT NULL,
                level TEXT,
                level_category TEXT,
                memo TEXT,
                updated_at DATE NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX industry_map_lookup_idx ON public.industry_map (industry_id, corp_code, level, is_primary)"
        )


def create_industry_table(connection: psycopg.Connection[Any], table_name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE public.{} (
                    corp_code TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    corp_name TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    fs_div TEXT,
                    sj_div TEXT,
                    account_name TEXT NOT NULL,
                    amount NUMERIC,
                    memo TEXT,
                    updated_at DATE NOT NULL
                )
                """
            ).format(sql.Identifier(table_name))
        )
        cursor.execute(
            sql.SQL("CREATE INDEX {} ON public.{} (corp_code, year, account_name)").format(
                sql.Identifier(f"{table_name}_lookup_idx"),
                sql.Identifier(table_name),
            )
        )


def drop_public_tables(connection: psycopg.Connection[Any], table_names: list[str]) -> None:
    if not table_names:
        return
    with connection.cursor() as cursor:
        for table_name in table_names:
            cursor.execute(sql.SQL("DROP TABLE IF EXISTS public.{}").format(sql.Identifier(table_name)))


def copy_rows(
    connection: psycopg.Connection[Any],
    table_name: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
) -> None:
    quoted_columns = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    with connection.cursor() as cursor:
        with cursor.copy(
            sql.SQL("COPY public.{} ({}) FROM STDIN").format(
                sql.Identifier(table_name),
                quoted_columns,
            )
        ) as copy:
            for row in rows:
                copy.write_row(row)


def add_unclassified_industry_mappings(
    *,
    industry_map_rows: list[tuple[Any, ...]],
    industry_rows: dict[str, list[tuple[Any, ...]]],
    default_updated_at: date,
) -> list[tuple[Any, ...]]:
    """Add safe placeholder memberships for an approved incomplete bundle.

    These members remain outside A/B/C peer scopes. The mapping makes the
    industry discoverable while preventing an invented peer-group assignment.
    """
    existing = {(industry_id, corp_code) for corp_code, _, _, industry_id, *_ in industry_map_rows}
    company_industries = {corp_code for corp_code, *_ in industry_map_rows}
    generated: list[tuple[Any, ...]] = []
    for industry_id, rows in industry_rows.items():
        for corp_code, stock_code, corp_name, *_ in rows:
            key = (industry_id, corp_code)
            if key in existing:
                continue
            generated.append(
                (
                    corp_code,
                    stock_code,
                    corp_name,
                    industry_id,
                    corp_code not in company_industries,
                    "UNCLASSIFIED",
                    "미분류",
                    "자동 생성: 비교그룹(A/B/C) 미분류",
                    default_updated_at,
                )
            )
            existing.add(key)
    return industry_map_rows + generated


def validate_and_load_bundle(
    bundle: CsvBundle,
    *,
    default_updated_at: date | None = None,
    auto_map_unclassified_industries: bool = False,
    reconcile_stock_codes: bool = False,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], dict[str, list[tuple[Any, ...]]], list[tuple[str, str, str, str]]]:
    companies_rows, master = load_companies_basic(bundle.companies_basic_path, default_updated_at=default_updated_at)
    stock_code_corrections: list[tuple[str, str, str, str]] = []
    if reconcile_stock_codes:
        companies_rows, stock_code_corrections = reconcile_master_stock_codes(
            companies_rows=companies_rows,
            master=master,
            industry_table_paths=bundle.industry_table_paths,
        )
    industry_map_rows = load_industry_map(
        bundle.industry_map_path,
        master,
        reconcile_stock_codes=reconcile_stock_codes,
    )
    industry_rows = {
        table_name: load_industry_table(path, master, default_updated_at=default_updated_at)
        for table_name, path in sorted(bundle.industry_table_paths.items())
    }
    if auto_map_unclassified_industries:
        if default_updated_at is None:
            raise ValueError("--auto-map-unclassified-industries requires --default-updated-at.")
        industry_map_rows = add_unclassified_industry_mappings(
            industry_map_rows=industry_map_rows,
            industry_rows=industry_rows,
            default_updated_at=default_updated_at,
        )
    return companies_rows, industry_map_rows, industry_rows, stock_code_corrections


def upload_bundle(
    *,
    database_url: str,
    companies_rows: list[tuple[Any, ...]],
    industry_map_rows: list[tuple[Any, ...]],
    industry_rows: dict[str, list[tuple[Any, ...]]],
    drop_all_public_tables: bool,
) -> None:
    target_tables = ["companies_basic", "industry_map", *industry_rows.keys()]
    tables_to_drop = sorted(set(target_tables + KNOWN_LEGACY_TABLES))

    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            if drop_all_public_tables:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                        """
                    )
                    all_tables = [row[0] for row in cursor.fetchall()]
                drop_public_tables(connection, all_tables)
            else:
                drop_public_tables(connection, tables_to_drop)

            create_companies_basic_table(connection)
            create_industry_map_table(connection)
            for table_name in industry_rows:
                create_industry_table(connection, table_name)

            copy_rows(connection, "companies_basic", COMPANIES_BASIC_HEADERS + [
                "revenue_recognition_basis",
                "revenue_recognition_code",
                "classification",
            ], companies_rows)
            copy_rows(connection, "industry_map", INDUSTRY_MAP_HEADERS, industry_map_rows)
            for table_name, rows in industry_rows.items():
                copy_rows(connection, table_name, INDUSTRY_TABLE_HEADERS, rows)

    print("Supabase upload completed.")
    print(f"- companies_basic: {len(companies_rows):,} rows")
    print(f"- industry_map: {len(industry_map_rows):,} rows")
    for table_name, rows in industry_rows.items():
        print(f"- {table_name}: {len(rows):,} rows")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and upload CSV bundle in upload/ to Supabase.")
    parser.add_argument(
        "--upload-dir",
        type=Path,
        default=DEFAULT_UPLOAD_DIR,
        help=f"Directory containing CSV upload files. Default: {DEFAULT_UPLOAD_DIR}",
    )
    parser.add_argument(
        "--default-updated-at",
        type=date.fromisoformat,
        help="Approved fallback date for blank companies_basic.updated_at values (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--auto-map-unclassified-industries",
        action="store_true",
        help="Create UNCLASSIFIED memberships for industry-table companies missing from industry_map.",
    )
    parser.add_argument(
        "--reconcile-stock-codes",
        action="store_true",
        help="Reconcile matching company-master stock codes from internally consistent financial CSVs.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate CSV files without uploading to Supabase.",
    )
    parser.add_argument(
        "--drop-all-public-tables",
        action="store_true",
        help="Drop every table in the public schema before recreating the upload tables.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bundle = discover_bundle(args.upload_dir)
    companies_rows, industry_map_rows, industry_rows, stock_code_corrections = validate_and_load_bundle(
        bundle,
        default_updated_at=args.default_updated_at,
        auto_map_unclassified_industries=args.auto_map_unclassified_industries,
        reconcile_stock_codes=args.reconcile_stock_codes,
    )

    print("Validation completed.")
    print(f"- companies_basic: {len(companies_rows):,} rows")
    print(f"- industry_map: {len(industry_map_rows):,} rows")
    for table_name, rows in industry_rows.items():
        print(f"- {table_name}: {len(rows):,} rows")
    if stock_code_corrections:
        print(f"- reconciled stock codes: {len(stock_code_corrections):,}")
        for corp_code, corp_name, previous, current in stock_code_corrections:
            print(f"  - {corp_code} {corp_name}: {previous} -> {current}")

    if args.validate_only:
        return

    database_url = get_database_url()
    upload_bundle(
        database_url=database_url,
        companies_rows=companies_rows,
        industry_map_rows=industry_map_rows,
        industry_rows=industry_rows,
        drop_all_public_tables=args.drop_all_public_tables,
    )


if __name__ == "__main__":
    main()
