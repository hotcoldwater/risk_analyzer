from __future__ import annotations

import argparse
import csv
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


def parse_amount(value: str, row_number: int, path: Path) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    normalized = stripped.replace(",", "")
    if normalized.startswith("+"):
        normalized = normalized[1:]
    if not normalized or normalized == "-":
        raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    if normalized.startswith("-"):
        body = normalized[1:]
        if not body.isdigit():
            raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    elif not normalized.isdigit():
        raise ValueError(f"{path.name}:{row_number} invalid amount: {value}")
    return int(normalized)


def validate_headers(path: Path, expected_headers: list[str]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"{path.name} is empty") from error
    if headers != expected_headers:
        raise ValueError(f"{path.name} header mismatch: expected={expected_headers}, actual={headers}")


def load_companies_basic(path: Path) -> tuple[list[tuple[Any, ...]], dict[str, dict[str, str]]]:
    validate_headers(path, COMPANIES_BASIC_HEADERS)
    rows: list[tuple[Any, ...]] = []
    master: dict[str, dict[str, str]] = {}

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            corp_code = row["corp_code"].strip()
            stock_code = row["stock_code"].strip()
            corp_name = row["corp_name"].strip()

            if not (corp_code.isdigit() and len(corp_code) == 8):
                raise ValueError(f"{path.name}:{row_number} invalid corp_code: {corp_code}")
            if not (stock_code.isalnum() and len(stock_code) == 6):
                raise ValueError(f"{path.name}:{row_number} invalid stock_code: {stock_code}")
            if not corp_name:
                raise ValueError(f"{path.name}:{row_number} corp_name is required")
            if corp_code in master:
                raise ValueError(f"{path.name}:{row_number} duplicated corp_code: {corp_code}")

            updated_at = parse_date(row["updated_at"].strip(), "updated_at", row_number, path)
            master[corp_code] = {
                "corp_code": corp_code,
                "stock_code": stock_code,
                "corp_name": corp_name,
            }
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


def load_industry_map(path: Path, master: dict[str, dict[str, str]]) -> list[tuple[Any, ...]]:
    validate_headers(path, INDUSTRY_MAP_HEADERS)
    rows: list[tuple[Any, ...]] = []
    seen_keys: set[tuple[str, str]] = set()

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            corp_code = row["corp_code"].strip()
            stock_code = row["stock_code"].strip()
            corp_name = row["corp_name"].strip()
            industry_id = row["industry_id"].strip()

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
) -> list[tuple[Any, ...]]:
    validate_headers(path, INDUSTRY_TABLE_HEADERS)
    rows: list[tuple[Any, ...]] = []

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            corp_code = row["corp_code"].strip()
            stock_code = row["stock_code"].strip()
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
                    parse_date(row["updated_at"].strip(), "updated_at", row_number, path),
                )
            )

    return rows


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
                updated_at DATE NOT NULL
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


def validate_and_load_bundle(bundle: CsvBundle) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], dict[str, list[tuple[Any, ...]]]]:
    companies_rows, master = load_companies_basic(bundle.companies_basic_path)
    industry_map_rows = load_industry_map(bundle.industry_map_path, master)
    industry_rows = {
        table_name: load_industry_table(path, master)
        for table_name, path in sorted(bundle.industry_table_paths.items())
    }
    return companies_rows, industry_map_rows, industry_rows


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

            copy_rows(connection, "companies_basic", COMPANIES_BASIC_HEADERS, companies_rows)
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
    companies_rows, industry_map_rows, industry_rows = validate_and_load_bundle(bundle)

    print("Validation completed.")
    print(f"- companies_basic: {len(companies_rows):,} rows")
    print(f"- industry_map: {len(industry_map_rows):,} rows")
    for table_name, rows in industry_rows.items():
        print(f"- {table_name}: {len(rows):,} rows")

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
