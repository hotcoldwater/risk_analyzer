from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import get_settings


def get_database_path() -> Path:
    settings = get_settings()
    return Path(settings.database_path)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_statements (
                corp_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                business_year TEXT NOT NULL,
                statement_type TEXT NOT NULL,
                liabilities REAL NOT NULL,
                equity REAL NOT NULL,
                debt_ratio REAL NOT NULL,
                unit TEXT NOT NULL,
                liabilities_account_name TEXT NOT NULL,
                equity_account_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (corp_code, business_year, statement_type)
            )
            """
        )

