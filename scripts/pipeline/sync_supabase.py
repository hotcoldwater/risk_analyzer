from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_DB = PROJECT_ROOT / "data" / "processed" / "server" / "dart_server.db"
BACKEND_ENV = PROJECT_ROOT / "backend" / ".env"

TABLES = ["companies", "financials", "account_coverage", "supported_analyses"]


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


def require_server_db() -> None:
    if not SERVER_DB.exists():
        raise FileNotFoundError(f"Service DB not found: {SERVER_DB}")


def fetch_sqlite_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def fetch_postgres_columns(connection: psycopg.Connection, table_name: str) -> list[str]:
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %(table_name)s
        ORDER BY ordinal_position
    """
    with connection.cursor() as cursor:
        cursor.execute(query, {"table_name": table_name})
        return [row[0] for row in cursor.fetchall()]


def truncate_tables(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        for table_name in TABLES:
            cursor.execute(sql.SQL("TRUNCATE TABLE public.{}").format(sql.Identifier(table_name)))


def copy_table(sqlite_connection: sqlite3.Connection, postgres_connection: psycopg.Connection, table_name: str) -> int:
    sqlite_columns = fetch_sqlite_columns(sqlite_connection, table_name)
    postgres_columns = fetch_postgres_columns(postgres_connection, table_name)

    if sqlite_columns != postgres_columns:
        raise RuntimeError(
            f"Column mismatch for {table_name}: sqlite={sqlite_columns}, postgres={postgres_columns}"
        )

    quoted_columns = sql.SQL(", ").join(sql.Identifier(column) for column in sqlite_columns)
    select_query = f"SELECT {', '.join(sqlite_columns)} FROM {table_name}"
    rows = sqlite_connection.execute(select_query).fetchall()

    with postgres_connection.cursor() as cursor:
        with cursor.copy(
            sql.SQL("COPY public.{} ({}) FROM STDIN").format(
                sql.Identifier(table_name),
                quoted_columns,
            )
        ) as copy:
            for row in rows:
                copy.write_row(row)

    return len(rows)


def print_remote_counts(connection: psycopg.Connection) -> None:
    with connection.cursor(row_factory=dict_row) as cursor:
        for table_name in TABLES:
            cursor.execute(sql.SQL("SELECT COUNT(*) AS row_count FROM public.{}").format(sql.Identifier(table_name)))
            row = cursor.fetchone()
            print(f"{table_name}: {row['row_count']:,}")


def main() -> None:
    require_server_db()
    database_url = get_database_url()

    with sqlite3.connect(SERVER_DB) as sqlite_connection, psycopg.connect(database_url) as postgres_connection:
        truncate_tables(postgres_connection)

        for table_name in TABLES:
            row_count = copy_table(sqlite_connection, postgres_connection, table_name)
            print(f"uploaded {table_name}: {row_count:,} rows")

        postgres_connection.commit()
        print_remote_counts(postgres_connection)


if __name__ == "__main__":
    main()
