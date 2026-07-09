"""DART raw extractor for a curated corp_code list.

The extractor is designed for industry-focused collection where the user
provides a small list of target corp_codes instead of scanning full markets.

It stores:
- company metadata
- full financial statements (`fnlttSinglAcntAll`)
- optional major accounts (`fnlttSinglAcnt`)
- optional raw XBRL documents

into one SQLite database under `data/raw/dart/`.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sqlite3
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from xml.etree import ElementTree


DART_BASE_URL = "https://opendart.fss.or.kr/api"
NAVER_MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
DEFAULT_DB_PATH = Path("data/workspace/dart/dart_dataset.db")
DEFAULT_EXPORT_DIR = Path("data/workspace/dart/exports")
DEFAULT_XBRL_DIR = Path("data/workspace/dart/xbrl")
DEFAULT_KSIC_PATH = Path("data/raw/reference/한국표준산업분류표(제11차).xlsx")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ANNUAL_REPORT_CODE = "11011"
REQUEST_TIMEOUT_SECONDS = 30
MARKET_TO_SOSOK = {"KOSPI": "0", "KOSDAQ": "1"}
SUPPORTED_MARKETS = ("KOSPI", "KOSDAQ", "ALL")
REPORT_CODE_ALIASES = {
    "annual": "11011",
    "half": "11012",
    "q1": "11013",
    "q3": "11014",
}
REPORT_CODE_LABELS = {
    "11011": "annual",
    "11012": "half",
    "11013": "q1",
    "11014": "q3",
}
STATEMENT_SCOPES = {"statements", "major_accounts", "xbrl"}
SCOPE_ALIASES = {
    "notes": "xbrl",
}
STATEMENT_BASE_ALIASES = {
    "consolidated": "CFS",
    "separate": "OFS",
    "cfs": "CFS",
    "ofs": "OFS",
}
CORP_CLASS_TO_MARKET = {
    "Y": "KOSPI",
    "K": "KOSDAQ",
    "N": "KONEX",
    "E": "ETC",
}


class DatasetError(RuntimeError):
    """Raised when remote data is missing or malformed."""


@dataclass(slots=True)
class CompanySelection:
    """One company selected from the market-cap ranking page."""

    market: str
    market_rank: int
    stock_code: str
    corp_name: str
    market_cap_krw: int
    current_price_krw: int


@dataclass(slots=True)
class CompanyDetails:
    """Company metadata resolved from DART plus KSIC classification."""

    corp_code: str
    corp_name: str
    stock_code: str
    market: str
    market_rank: int
    market_cap_krw: int
    current_price_krw: int
    dart_modify_date: str | None
    dart_sector_name: str | None
    ksic_macro_sector: str | None


@dataclass(slots=True)
class CorpCodeEntry:
    corp_code: str
    stock_code: str
    corp_name: str
    modify_date: str | None


@dataclass(slots=True)
class XbrlDocument:
    corp_code: str
    stock_code: str
    corp_name: str
    bsns_year: str
    reprt_code: str
    rcept_no: str
    local_path: str
    fetched_at: str


class SimpleEnvLoader:
    """Tiny .env reader to avoid adding another runtime dependency."""

    @staticmethod
    def load(path: Path = Path(".env")) -> None:
        if not path.exists():
            return

        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


class Database:
    """SQLite wrapper that keeps schema creation and upsert logic in one place."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.create_schema()

    def create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                corp_code TEXT PRIMARY KEY,
                corp_name TEXT NOT NULL,
                stock_code TEXT NOT NULL UNIQUE,
                market TEXT NOT NULL,
                market_rank INTEGER NOT NULL,
                market_cap_krw INTEGER NOT NULL,
                current_price_krw INTEGER NOT NULL,
                dart_modify_date TEXT,
                dart_sector_name TEXT,
                ksic_macro_sector TEXT,
                selected_on TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS financial_statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                corp_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                bsns_year TEXT NOT NULL,
                reprt_code TEXT NOT NULL,
                fs_div TEXT,
                fs_nm TEXT,
                sj_div TEXT,
                sj_nm TEXT,
                account_id TEXT,
                account_nm TEXT,
                account_detail TEXT,
                thstrm_nm TEXT,
                thstrm_amount TEXT,
                thstrm_add_amount TEXT,
                frmtrm_nm TEXT,
                frmtrm_amount TEXT,
                frmtrm_q_nm TEXT,
                frmtrm_q_amount TEXT,
                bfefrmtrm_nm TEXT,
                bfefrmtrm_amount TEXT,
                ord TEXT,
                currency TEXT,
                source_status TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                FOREIGN KEY (corp_code) REFERENCES companies(corp_code)
            );

            CREATE INDEX IF NOT EXISTS idx_financials_company_year
            ON financial_statements (corp_code, bsns_year);

            CREATE INDEX IF NOT EXISTS idx_financials_company_year_fs_div
            ON financial_statements (corp_code, bsns_year, fs_div);

            CREATE TABLE IF NOT EXISTS major_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                corp_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                bsns_year TEXT NOT NULL,
                reprt_code TEXT NOT NULL,
                account_nm TEXT,
                sj_div TEXT,
                sj_nm TEXT,
                amount TEXT,
                source_status TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                FOREIGN KEY (corp_code) REFERENCES companies(corp_code)
            );

            CREATE INDEX IF NOT EXISTS idx_major_accounts_company_year
            ON major_accounts (corp_code, bsns_year, reprt_code);

            CREATE TABLE IF NOT EXISTS xbrl_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                corp_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                bsns_year TEXT NOT NULL,
                reprt_code TEXT NOT NULL,
                rcept_no TEXT NOT NULL,
                local_path TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                UNIQUE(corp_code, bsns_year, reprt_code, rcept_no),
                FOREIGN KEY (corp_code) REFERENCES companies(corp_code)
            );

            CREATE TABLE IF NOT EXISTS fetch_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                market TEXT NOT NULL,
                company_limit INTEGER NOT NULL,
                year_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS fetch_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                corp_code TEXT,
                corp_name TEXT,
                stock_code TEXT,
                market TEXT,
                bsns_year INTEGER,
                fs_div TEXT,
                stage TEXT NOT NULL,
                error_message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES fetch_runs(id)
            );
            """
        )
        self._ensure_column("companies", "dart_sector_name", "TEXT")
        self._ensure_column("companies", "ksic_macro_sector", "TEXT")
        self._create_preferred_financials_table()
        self._bootstrap_preferred_financials()
        self.connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, column_definition: str) -> None:
        columns = self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_names = {row[1] for row in columns}
        if column_name not in existing_names:
            self.connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    def _create_preferred_financials_table(self) -> None:
        existing_object = self.connection.execute(
            "SELECT type FROM sqlite_master WHERE name = 'preferred_financial_statements'"
        ).fetchone()
        if existing_object and existing_object[0] == "view":
            self.connection.execute("DROP VIEW IF EXISTS preferred_financial_statements")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS preferred_financial_statements (
                id INTEGER PRIMARY KEY,
                corp_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                corp_name TEXT NOT NULL,
                bsns_year TEXT NOT NULL,
                reprt_code TEXT NOT NULL,
                fs_div TEXT,
                fs_nm TEXT,
                sj_div TEXT,
                sj_nm TEXT,
                account_id TEXT,
                account_nm TEXT,
                account_detail TEXT,
                thstrm_nm TEXT,
                thstrm_amount TEXT,
                thstrm_add_amount TEXT,
                frmtrm_nm TEXT,
                frmtrm_amount TEXT,
                frmtrm_q_nm TEXT,
                frmtrm_q_amount TEXT,
                bfefrmtrm_nm TEXT,
                bfefrmtrm_amount TEXT,
                ord TEXT,
                currency TEXT,
                source_status TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                statement_basis TEXT NOT NULL,
                used_fallback INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_preferred_financials_company_year
            ON preferred_financial_statements (corp_code, bsns_year, reprt_code);
            """
        )

    def _bootstrap_preferred_financials(self) -> None:
        raw_count = self.connection.execute(
            "SELECT COUNT(*) FROM financial_statements"
        ).fetchone()[0]
        preferred_count = self.connection.execute(
            "SELECT COUNT(*) FROM preferred_financial_statements"
        ).fetchone()[0]
        if raw_count == 0 or preferred_count > 0:
            return
        self.rebuild_preferred_financials()

    def rebuild_preferred_financials(self) -> None:
        self.connection.execute("DELETE FROM preferred_financial_statements")
        self.connection.execute(
            """
            INSERT INTO preferred_financial_statements (
                id, corp_code, stock_code, corp_name, bsns_year, reprt_code,
                fs_div, fs_nm, sj_div, sj_nm, account_id, account_nm,
                account_detail, thstrm_nm, thstrm_amount, thstrm_add_amount,
                frmtrm_nm, frmtrm_amount, frmtrm_q_nm, frmtrm_q_amount,
                bfefrmtrm_nm, bfefrmtrm_amount, ord, currency, source_status,
                fetched_at, raw_payload_json, statement_basis, used_fallback
            )
            WITH preferred_basis AS (
                SELECT
                    corp_code,
                    bsns_year,
                    reprt_code,
                    CASE
                        WHEN MAX(CASE WHEN fs_div = 'CFS' THEN 1 ELSE 0 END) = 1 THEN 'CFS'
                        WHEN MAX(CASE WHEN fs_div = 'OFS' THEN 1 ELSE 0 END) = 1 THEN 'OFS'
                        ELSE NULL
                    END AS statement_basis
                FROM financial_statements
                GROUP BY corp_code, bsns_year, reprt_code
            )
            SELECT
                f.id, f.corp_code, f.stock_code, f.corp_name, f.bsns_year, f.reprt_code,
                f.fs_div, f.fs_nm, f.sj_div, f.sj_nm, f.account_id, f.account_nm,
                f.account_detail, f.thstrm_nm, f.thstrm_amount, f.thstrm_add_amount,
                f.frmtrm_nm, f.frmtrm_amount, f.frmtrm_q_nm, f.frmtrm_q_amount,
                f.bfefrmtrm_nm, f.bfefrmtrm_amount, f.ord, f.currency, f.source_status,
                f.fetched_at, f.raw_payload_json,
                preferred_basis.statement_basis,
                CASE preferred_basis.statement_basis WHEN 'OFS' THEN 1 ELSE 0 END
            FROM financial_statements f
            JOIN preferred_basis
              ON preferred_basis.corp_code = f.corp_code
             AND preferred_basis.bsns_year = f.bsns_year
             AND preferred_basis.reprt_code = f.reprt_code
             AND preferred_basis.statement_basis = f.fs_div
            """
        )
        self.connection.commit()

    def refresh_preferred_financial_rows(self, corp_code: str, year: int, reprt_code: str) -> None:
        year_text = str(year)
        self.connection.execute(
            "DELETE FROM preferred_financial_statements WHERE corp_code = ? AND bsns_year = ? AND reprt_code = ?",
            (corp_code, year_text, reprt_code),
        )
        self.connection.execute(
            """
            INSERT INTO preferred_financial_statements (
                id, corp_code, stock_code, corp_name, bsns_year, reprt_code,
                fs_div, fs_nm, sj_div, sj_nm, account_id, account_nm,
                account_detail, thstrm_nm, thstrm_amount, thstrm_add_amount,
                frmtrm_nm, frmtrm_amount, frmtrm_q_nm, frmtrm_q_amount,
                bfefrmtrm_nm, bfefrmtrm_amount, ord, currency, source_status,
                fetched_at, raw_payload_json, statement_basis, used_fallback
            )
            SELECT
                f.id, f.corp_code, f.stock_code, f.corp_name, f.bsns_year, f.reprt_code,
                f.fs_div, f.fs_nm, f.sj_div, f.sj_nm, f.account_id, f.account_nm,
                f.account_detail, f.thstrm_nm, f.thstrm_amount, f.thstrm_add_amount,
                f.frmtrm_nm, f.frmtrm_amount, f.frmtrm_q_nm, f.frmtrm_q_amount,
                f.bfefrmtrm_nm, f.bfefrmtrm_amount, f.ord, f.currency, f.source_status,
                f.fetched_at, f.raw_payload_json,
                basis.statement_basis,
                CASE basis.statement_basis WHEN 'OFS' THEN 1 ELSE 0 END
            FROM financial_statements f
            JOIN (
                SELECT
                    corp_code,
                    bsns_year,
                    reprt_code,
                    CASE
                        WHEN MAX(CASE WHEN fs_div = 'CFS' THEN 1 ELSE 0 END) = 1 THEN 'CFS'
                        WHEN MAX(CASE WHEN fs_div = 'OFS' THEN 1 ELSE 0 END) = 1 THEN 'OFS'
                        ELSE NULL
                    END AS statement_basis
                FROM financial_statements
                WHERE corp_code = ? AND bsns_year = ? AND reprt_code = ?
                GROUP BY corp_code, bsns_year, reprt_code
            ) AS basis
              ON basis.corp_code = f.corp_code
             AND basis.bsns_year = f.bsns_year
             AND basis.reprt_code = f.reprt_code
             AND basis.statement_basis = f.fs_div
            WHERE f.corp_code = ? AND f.bsns_year = ? AND f.reprt_code = ?
            """,
            (corp_code, year_text, reprt_code, corp_code, year_text, reprt_code),
        )
        self.connection.commit()

    def start_run(self, market: str, company_limit: int, year_count: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO fetch_runs (started_at, market, company_limit, year_count, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (utc_now(), market, company_limit, year_count, "running"),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, note: str | None = None) -> None:
        self.connection.execute(
            """
            UPDATE fetch_runs
            SET finished_at = ?, status = ?, note = ?
            WHERE id = ?
            """,
            (utc_now(), status, note, run_id),
        )
        self.connection.commit()

    def upsert_company(
        self,
        company: CompanyDetails,
    ) -> None:
        now = utc_now()
        self.connection.execute(
            """
            INSERT INTO companies (
                corp_code, corp_name, stock_code, market, market_rank,
                market_cap_krw, current_price_krw, dart_modify_date,
                dart_sector_name, ksic_macro_sector,
                selected_on, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(corp_code) DO UPDATE SET
                corp_name = excluded.corp_name,
                stock_code = excluded.stock_code,
                market = excluded.market,
                market_rank = excluded.market_rank,
                market_cap_krw = excluded.market_cap_krw,
                current_price_krw = excluded.current_price_krw,
                dart_modify_date = excluded.dart_modify_date,
                dart_sector_name = excluded.dart_sector_name,
                ksic_macro_sector = excluded.ksic_macro_sector,
                selected_on = excluded.selected_on,
                updated_at = excluded.updated_at
            """,
            (
                company.corp_code,
                company.corp_name,
                company.stock_code,
                company.market,
                company.market_rank,
                company.market_cap_krw,
                company.current_price_krw,
                company.dart_modify_date,
                company.dart_sector_name,
                company.ksic_macro_sector,
                date.today().isoformat(),
                now,
                now,
            ),
        )
        self.connection.commit()

    def record_failure(
        self,
        run_id: int,
        company: CompanyDetails | None,
        error_message: str,
        stage: str,
        business_year: int | None = None,
        fs_division: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO fetch_failures (
                run_id, corp_code, corp_name, stock_code, market,
                bsns_year, fs_div, stage, error_message, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                company.corp_code if company else None,
                company.corp_name if company else None,
                company.stock_code if company else None,
                company.market if company else None,
                business_year,
                fs_division,
                stage,
                error_message,
                utc_now(),
            ),
        )
        self.connection.commit()

    def replace_financial_rows(
        self,
        corp_code: str,
        stock_code: str,
        corp_name: str,
        year: int,
        reprt_code: str,
        fs_division: str,
        rows: list[dict[str, Any]],
        source_status: str,
    ) -> None:
        fetched_at = utc_now()
        self.connection.execute(
            """
            DELETE FROM financial_statements
            WHERE corp_code = ? AND bsns_year = ? AND reprt_code = ? AND fs_div = ?
            """,
            (corp_code, str(year), reprt_code, fs_division),
        )

        for row in rows:
            payload_row = dict(row)
            payload_row["fs_div"] = fs_division
            payload_row.setdefault("reprt_code", reprt_code)
            self.connection.execute(
                """
                INSERT INTO financial_statements (
                    corp_code, stock_code, corp_name, bsns_year, reprt_code,
                    fs_div, fs_nm, sj_div, sj_nm, account_id, account_nm,
                    account_detail, thstrm_nm, thstrm_amount, thstrm_add_amount,
                    frmtrm_nm, frmtrm_amount, frmtrm_q_nm, frmtrm_q_amount,
                    bfefrmtrm_nm, bfefrmtrm_amount, ord, currency,
                    source_status, fetched_at, raw_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    corp_code,
                    stock_code,
                    corp_name,
                    str(year),
                    payload_row.get("reprt_code", ANNUAL_REPORT_CODE),
                    fs_division,
                    row.get("fs_nm"),
                    row.get("sj_div"),
                    row.get("sj_nm"),
                    row.get("account_id"),
                    row.get("account_nm"),
                    row.get("account_detail"),
                    row.get("thstrm_nm"),
                    row.get("thstrm_amount"),
                    row.get("thstrm_add_amount"),
                    row.get("frmtrm_nm"),
                    row.get("frmtrm_amount"),
                    row.get("frmtrm_q_nm"),
                    row.get("frmtrm_q_amount"),
                    row.get("bfefrmtrm_nm"),
                    row.get("bfefrmtrm_amount"),
                    row.get("ord"),
                    row.get("currency"),
                    source_status,
                    fetched_at,
                    stable_json_dump(payload_row),
                ),
            )

        self.connection.commit()
        self.refresh_preferred_financial_rows(corp_code, year, reprt_code)

    def replace_major_account_rows(
        self,
        corp_code: str,
        stock_code: str,
        corp_name: str,
        year: int,
        reprt_code: str,
        rows: list[dict[str, Any]],
        source_status: str,
    ) -> None:
        fetched_at = utc_now()
        self.connection.execute(
            "DELETE FROM major_accounts WHERE corp_code = ? AND bsns_year = ? AND reprt_code = ?",
            (corp_code, str(year), reprt_code),
        )
        for row in rows:
            amount = (
                row.get("thstrm_amount")
                or row.get("thstrm_add_amount")
                or row.get("frmtrm_amount")
                or row.get("amount")
            )
            self.connection.execute(
                """
                INSERT INTO major_accounts (
                    corp_code, stock_code, corp_name, bsns_year, reprt_code,
                    account_nm, sj_div, sj_nm, amount, source_status, fetched_at, raw_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    corp_code,
                    stock_code,
                    corp_name,
                    str(year),
                    reprt_code,
                    row.get("account_nm"),
                    row.get("sj_div"),
                    row.get("sj_nm"),
                    amount,
                    source_status,
                    fetched_at,
                    stable_json_dump(row),
                ),
            )
        self.connection.commit()

    def upsert_xbrl_document(self, document: XbrlDocument) -> None:
        self.connection.execute(
            """
            INSERT INTO xbrl_documents (
                corp_code, stock_code, corp_name, bsns_year, reprt_code, rcept_no, local_path, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(corp_code, bsns_year, reprt_code, rcept_no) DO UPDATE SET
                local_path = excluded.local_path,
                fetched_at = excluded.fetched_at
            """,
            (
                document.corp_code,
                document.stock_code,
                document.corp_name,
                document.bsns_year,
                document.reprt_code,
                document.rcept_no,
                document.local_path,
                document.fetched_at,
            ),
        )
        self.connection.commit()

    def export_company_csvs(self, export_dir: Path) -> list[Path]:
        export_dir.mkdir(parents=True, exist_ok=True)
        exported_files: list[Path] = []
        master_csv_path = export_dir / "companies.csv"
        self._export_companies_master_csv(master_csv_path)
        if master_csv_path.exists():
            exported_files.append(master_csv_path)
        preferred_csv_path = export_dir / "preferred_financial_statements.csv"
        self._export_preferred_financials_csv(preferred_csv_path)
        if preferred_csv_path.exists():
            exported_files.append(preferred_csv_path)
        major_accounts_csv_path = export_dir / "major_accounts.csv"
        self._export_major_accounts_csv(major_accounts_csv_path)
        if major_accounts_csv_path.exists():
            exported_files.append(major_accounts_csv_path)
        xbrl_csv_path = export_dir / "xbrl_documents.csv"
        self._export_xbrl_documents_csv(xbrl_csv_path)
        if xbrl_csv_path.exists():
            exported_files.append(xbrl_csv_path)
        company_rows = self.connection.execute(
            "SELECT corp_code, corp_name FROM companies ORDER BY market, market_rank"
        ).fetchall()
        for company in company_rows:
            target_path = export_dir / f"{company['corp_code']}.csv"
            financial_rows = self.connection.execute(
                """
                SELECT corp_code, stock_code, corp_name, bsns_year, reprt_code, fs_div, fs_nm,
                       sj_div, sj_nm, account_id, account_nm, account_detail, thstrm_nm,
                       thstrm_amount, thstrm_add_amount, frmtrm_nm, frmtrm_amount,
                       frmtrm_q_nm, frmtrm_q_amount, bfefrmtrm_nm, bfefrmtrm_amount,
                       ord, currency, source_status, fetched_at
                FROM financial_statements
                WHERE corp_code = ?
                ORDER BY bsns_year DESC, fs_div, sj_div, ord, account_nm
                """,
                (company["corp_code"],),
            ).fetchall()

            if not financial_rows:
                continue

            with target_path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(financial_rows[0].keys())
                for row in financial_rows:
                    writer.writerow(list(row))

            exported_files.append(target_path)

        return exported_files

    def _export_companies_master_csv(self, target_path: Path) -> None:
        company_rows = self.connection.execute(
            """
            SELECT corp_code, corp_name, stock_code, market, market_rank,
                   market_cap_krw, current_price_krw, dart_modify_date,
                   dart_sector_name, ksic_macro_sector,
                   selected_on, created_at, updated_at
            FROM companies
            ORDER BY market, market_rank
            """
        ).fetchall()

        if not company_rows:
            return

        with target_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(company_rows[0].keys())
            for row in company_rows:
                writer.writerow(list(row))

    def _export_preferred_financials_csv(self, target_path: Path) -> None:
        rows = self.connection.execute(
            """
            SELECT corp_code, stock_code, corp_name, bsns_year, reprt_code, fs_div, fs_nm,
                   sj_div, sj_nm, account_id, account_nm, account_detail, thstrm_nm,
                   thstrm_amount, thstrm_add_amount, frmtrm_nm, frmtrm_amount,
                   frmtrm_q_nm, frmtrm_q_amount, bfefrmtrm_nm, bfefrmtrm_amount,
                   ord, currency, source_status, fetched_at, statement_basis, used_fallback
            FROM preferred_financial_statements
            ORDER BY corp_code, bsns_year DESC, sj_div, ord, account_nm
            """
        ).fetchall()

        if not rows:
            return

        with target_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))

    def _export_major_accounts_csv(self, target_path: Path) -> None:
        rows = self.connection.execute(
            """
            SELECT corp_code, stock_code, corp_name, bsns_year, reprt_code,
                   account_nm, sj_div, sj_nm, amount, source_status, fetched_at
            FROM major_accounts
            ORDER BY corp_code, bsns_year DESC, reprt_code, account_nm
            """
        ).fetchall()
        if not rows:
            return
        with target_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))

    def _export_xbrl_documents_csv(self, target_path: Path) -> None:
        rows = self.connection.execute(
            """
            SELECT corp_code, stock_code, corp_name, bsns_year, reprt_code, rcept_no, local_path, fetched_at
            FROM xbrl_documents
            ORDER BY corp_code, bsns_year DESC, reprt_code
            """
        ).fetchall()
        if not rows:
            return
        with target_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))

    def close(self) -> None:
        self.connection.close()


class DartClient:
    """Thin client for the two DART endpoints this project currently needs."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def fetch_corp_codes(self) -> dict[str, dict[str, str]]:
        response = self.session.get(
            f"{DART_BASE_URL}/corpCode.xml",
            params={"crtfc_key": self.api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            xml_name = archive.namelist()[0]
            xml_bytes = archive.read(xml_name)

        root = ElementTree.fromstring(xml_bytes)
        result: dict[str, dict[str, str]] = {}

        for company_node in root.findall("list"):
            stock_code = clean_text(company_node.findtext("stock_code"))
            corp_code = clean_text(company_node.findtext("corp_code"))
            if not stock_code or not corp_code:
                continue

            result[stock_code] = {
                "corp_code": corp_code,
                "stock_code": stock_code,
                "corp_name": clean_text(company_node.findtext("corp_name")),
                "modify_date": clean_text(company_node.findtext("modify_date")),
            }

        return result

    def fetch_financial_statements(
        self,
        corp_code: str,
        business_year: int,
        report_code: str,
        fs_division: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        response = self.session.get(
            f"{DART_BASE_URL}/fnlttSinglAcntAll.json",
            params={
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": str(business_year),
                "reprt_code": report_code,
                "fs_div": fs_division,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        payload = response.json()
        status = clean_text(payload.get("status"))
        if status == "000":
            rows = payload.get("list") or []
            if not isinstance(rows, list):
                raise DatasetError("DART returned a non-list 'list' payload.")
            return status, rows

        # DART returns status codes like 013 when no data exists for that period.
        if status in {"013", "020"}:
            return status, []

        message = clean_text(payload.get("message")) or "Unknown DART error"
        raise DatasetError(
            f"DART error for {corp_code}/{business_year}/{report_code}/{fs_division}: {status} {message}"
        )

    def fetch_major_accounts(
        self,
        corp_code: str,
        business_year: int,
        report_code: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        response = self.session.get(
            f"{DART_BASE_URL}/fnlttSinglAcnt.json",
            params={
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": str(business_year),
                "reprt_code": report_code,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        payload = response.json()
        status = clean_text(payload.get("status"))
        if status == "000":
            rows = payload.get("list") or []
            if not isinstance(rows, list):
                raise DatasetError("DART returned a non-list 'list' payload for fnlttSinglAcnt.")
            return status, rows
        if status in {"013", "020"}:
            return status, []
        message = clean_text(payload.get("message")) or "Unknown DART error"
        raise DatasetError(f"DART error for major accounts {corp_code}/{business_year}/{report_code}: {status} {message}")

    def fetch_company_overview(self, corp_code: str) -> dict[str, Any]:
        response = self.session.get(
            f"{DART_BASE_URL}/company.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        status = clean_text(payload.get("status"))
        if status != "000":
            message = clean_text(payload.get("message")) or "Unknown DART error"
            raise DatasetError(f"DART company error for {corp_code}: {status} {message}")

        return payload


class MarketCapSelector:
    """Fetches market constituents from Naver Finance's market-cap table."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def fetch_market_companies(self, market: str, limit: int | None = None) -> list[CompanySelection]:
        if market not in MARKET_TO_SOSOK:
            raise DatasetError(f"Unsupported market: {market}")

        first_page_html = self._fetch_market_page(MARKET_TO_SOSOK[market], 1)
        total_pages = self._extract_page_count(first_page_html)

        selections: list[CompanySelection] = []
        seen_codes: set[str] = set()

        for page_number in range(1, total_pages + 1):
            html = first_page_html if page_number == 1 else self._fetch_market_page(MARKET_TO_SOSOK[market], page_number)
            table = self._read_market_sum_table(html)
            stock_rows = self._extract_stock_rows(html)
            cleaned = table.dropna(subset=["N", "종목명", "시가총액"]).copy().reset_index(drop=True)

            if len(stock_rows) < len(cleaned):
                raise DatasetError(f"Could not extract enough stock rows from {market} page {page_number}.")

            for index, row in cleaned.iterrows():
                stock_code, corp_name = stock_rows[index]
                if corp_name.strip() != str(row["종목명"]).strip():
                    raise DatasetError(
                        f"Row mismatch on {market} page {page_number}: "
                        f"table={row['종목명']} anchor={corp_name}"
                    )
                if stock_code in seen_codes:
                    continue

                seen_codes.add(stock_code)
                selections.append(
                    CompanySelection(
                        market=market,
                        market_rank=int(row["N"]),
                        stock_code=stock_code,
                        corp_name=corp_name.strip(),
                        market_cap_krw=int(row["시가총액"]) * 100_000_000,
                        current_price_krw=int(row["현재가"]),
                    )
                )

                if limit is not None and len(selections) >= limit:
                    return selections

        return selections

    def fetch_companies(self, market: str, limit: int | None = None) -> list[CompanySelection]:
        if market == "ALL":
            companies: list[CompanySelection] = []
            for single_market in ("KOSPI", "KOSDAQ"):
                companies.extend(self.fetch_market_companies(single_market, limit=None))
            return companies if limit is None else companies[:limit]

        return self.fetch_market_companies(market, limit=limit)

    def _fetch_market_page(self, sosok: str, page_number: int) -> str:
        response = self.session.get(
            NAVER_MARKET_SUM_URL.format(sosok=sosok, page=page_number),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return decode_kr_html(response.content)

    @staticmethod
    def _read_market_sum_table(html: str) -> pd.DataFrame:
        frames = pd.read_html(io.StringIO(html))
        for frame in frames:
            if {"N", "종목명", "시가총액", "현재가"}.issubset(frame.columns):
                return frame
        raise DatasetError("Could not find the KOSPI market-cap table in Naver Finance HTML.")

    @staticmethod
    def _extract_stock_rows(html: str) -> list[tuple[str, str]]:
        pattern = re.compile(r'<a href="/item/main\.naver\?code=([0-9A-Z]{6})" class="tltle">([^<]+)</a>')
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()

        for stock_code, corp_name in pattern.findall(html):
            if stock_code in seen:
                continue
            seen.add(stock_code)
            rows.append((stock_code, corp_name))

        return rows

    @staticmethod
    def _extract_page_count(html: str) -> int:
        page_numbers = [int(value) for value in re.findall(r"page=(\d+)", html)]
        if not page_numbers:
            return 1
        return max(page_numbers)


class KsicClassifier:
    """Resolves DART sector names into a normalized macro-sector label."""

    def __init__(self, excel_path: Path) -> None:
        self.excel_path = excel_path
        self.lookup: dict[str, str] = {}
        self.code_lookup: dict[str, str] = {}
        self.loaded = False

    def load(self) -> None:
        if not self.excel_path.exists():
            self.loaded = False
            return

        xls = pd.ExcelFile(self.excel_path)
        df = pd.read_excel(xls, sheet_name="11차개정한국표준산업분류", header=1)
        df.columns = [
            "대분류코드", "대분류명", "중분류코드", "중분류명", "소분류코드",
            "소분류명", "세분류코드", "세분류명", "세세분류코드", "세세분류명",
        ]
        df[
            ["대분류코드", "대분류명", "중분류코드", "중분류명", "소분류코드", "소분류명", "세분류코드", "세분류명"]
        ] = df[
            ["대분류코드", "대분류명", "중분류코드", "중분류명", "소분류코드", "소분류명", "세분류코드", "세분류명"]
        ].ffill()

        # 제조업은 중분류, 나머지는 대분류를 우선 쓰는 하이브리드 규칙.
        df["타겟_분류명"] = np.where(df["대분류코드"] == "C", df["중분류명"], df["대분류명"])

        for _, row in df.iterrows():
            target_value = clean_text(row["타겟_분류명"])
            for code_column in ("중분류코드", "소분류코드", "세분류코드", "세세분류코드"):
                code_value = normalize_ksic_code(row[code_column])
                if code_value and code_value not in self.code_lookup:
                    self.code_lookup[code_value] = target_value
            for column_name in ("소분류명", "중분류명", "세분류명", "세세분류명"):
                normalized = normalize_sector_text(row[column_name])
                if normalized and normalized not in self.lookup:
                    self.lookup[normalized] = target_value

        self.loaded = True

    def classify(self, dart_sector_name: str | None) -> str | None:
        if not dart_sector_name:
            return None
        code_text = normalize_ksic_code(dart_sector_name)
        if code_text.isdigit():
            for prefix_length in range(len(code_text), 0, -1):
                matched = self.code_lookup.get(code_text[:prefix_length])
                if matched:
                    return matched
        normalized = normalize_sector_text(dart_sector_name)
        if not normalized:
            return None
        return self.lookup.get(normalized, clean_text(dart_sector_name))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect DART raw data for a user-provided corp_code list."
    )
    parser.add_argument(
        "--corp-codes-file",
        type=Path,
        required=True,
        help="Text file with one corp_code per line. Lines starting with # are ignored.",
    )
    parser.add_argument(
        "--years",
        type=int,
        help="How many completed business years to fetch.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f"CSV export directory. Default: {DEFAULT_EXPORT_DIR}",
    )
    parser.add_argument(
        "--api-key",
        help="DART API key. Defaults to the DART_API_KEY environment variable.",
    )
    parser.add_argument(
        "--reports",
        default="annual",
        help="Comma-separated report aliases or codes. Supported aliases: annual, half, q1, q3, all.",
    )
    parser.add_argument(
        "--statement-bases",
        default="both",
        help="CFS, OFS, or both. Comma-separated values allowed.",
    )
    parser.add_argument(
        "--scopes",
        default="statements",
        help="Comma-separated scopes: statements, major_accounts, xbrl. 'notes' maps to raw XBRL, 'all' enables every implemented scope.",
    )
    parser.add_argument(
        "--xbrl-dir",
        type=Path,
        default=DEFAULT_XBRL_DIR,
        help=f"Directory for downloaded raw XBRL files. Default: {DEFAULT_XBRL_DIR}",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip optional company-level CSV exports after the SQLite update.",
    )
    parser.add_argument(
        "--request-sleep",
        type=float,
        default=0.1,
        help="Seconds to sleep between DART requests to reduce burst traffic.",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=2,
        help="How many times each DART request should be retried after the first failure. Default: 2.",
    )
    parser.add_argument(
        "--ksic-path",
        type=Path,
        default=DEFAULT_KSIC_PATH,
        help=f"KSIC Excel path for sector normalization. Default: {DEFAULT_KSIC_PATH}",
    )
    return parser.parse_args()


def prompt_for_year_count(initial_value: int | None) -> int:
    if initial_value is not None:
        validate_positive_integer(initial_value, "--years")
        return initial_value

    while True:
        raw = input("과거 몇 개년을 수집할까요? ").strip()
        try:
            value = int(raw)
            validate_positive_integer(value, "years")
            return value
        except ValueError as error:
            print(f"입력 오류: {error}")


def validate_positive_integer(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")


def resolved_api_key(cli_value: str | None) -> str:
    SimpleEnvLoader.load()
    SimpleEnvLoader.load(Path(__file__).with_name(".env"))
    api_key = cli_value or os.getenv("DART_API_KEY")
    if not api_key:
        raise DatasetError("DART API key is missing. Set DART_API_KEY in .env or pass --api-key.")
    return api_key


def load_corp_codes(file_path: Path) -> list[str]:
    if not file_path.exists():
        raise DatasetError(f"corp_code file not found: {file_path}")
    corp_codes: list[str] = []
    seen: set[str] = set()
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        corp_code = re.sub(r"[^0-9]", "", stripped)
        if len(corp_code) != 8:
            raise DatasetError(f"Invalid corp_code in {file_path}: {raw_line}")
        if corp_code in seen:
            continue
        seen.add(corp_code)
        corp_codes.append(corp_code)
    if not corp_codes:
        raise DatasetError(f"No corp_codes found in {file_path}")
    return corp_codes


def resolve_report_codes(cli_value: str) -> list[str]:
    tokens = [token.strip().lower() for token in cli_value.split(",") if token.strip()]
    if not tokens:
        raise DatasetError("At least one report code must be provided.")
    if "all" in tokens:
        return ["11011", "11012", "11013", "11014"]
    report_codes: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        code = REPORT_CODE_ALIASES.get(token, token)
        if code not in REPORT_CODE_LABELS:
            raise DatasetError(f"Unsupported report code: {token}")
        if code in seen:
            continue
        seen.add(code)
        report_codes.append(code)
    return report_codes


def resolve_statement_bases(cli_value: str) -> list[str]:
    tokens = [token.strip().lower() for token in cli_value.split(",") if token.strip()]
    if not tokens:
        raise DatasetError("At least one statement basis must be provided.")
    if "both" in tokens:
        return ["CFS", "OFS"]
    bases: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        basis = STATEMENT_BASE_ALIASES.get(token, token.upper())
        if basis not in {"CFS", "OFS"}:
            raise DatasetError(f"Unsupported statement basis: {token}")
        if basis in seen:
            continue
        seen.add(basis)
        bases.append(basis)
    return bases


def resolve_scopes(cli_value: str) -> list[str]:
    tokens = [token.strip().lower() for token in cli_value.split(",") if token.strip()]
    if not tokens:
        raise DatasetError("At least one scope must be provided.")
    if "all" in tokens:
        return ["statements", "major_accounts", "xbrl"]
    scopes: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        token = SCOPE_ALIASES.get(token, token)
        if token not in STATEMENT_SCOPES:
            raise DatasetError(f"Unsupported scope: {token}")
        if token in seen:
            continue
        seen.add(token)
        scopes.append(token)
    return scopes


def completed_business_years(year_count: int, today: date | None = None) -> list[int]:
    """Return the last N fully completed years.

    Annual reports for the current calendar year are not final yet, so the current
    year is excluded by design.
    """

    if today is None:
        today = date.today()

    final_year = today.year - 1
    return [final_year - offset for offset in range(year_count)]


def market_from_corp_cls(value: Any) -> str:
    normalized = clean_text(value).upper()
    return CORP_CLASS_TO_MARKET.get(normalized, "UNKNOWN")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def stable_json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_sector_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    text = re.sub(r"[ㆍ·\s;,\.~/\(\)\-]", "", text)
    text = text.replace("나", "및")
    return text.strip()


def normalize_ksic_code(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return re.sub(r"[^0-9]", "", text)


def decode_kr_html(content: bytes) -> str:
    for encoding in ("cp949", "euc-kr", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def fetch_with_retries(callback: Any, retry_count: int, sleep_seconds: float, retry_label: str) -> Any:
    last_error: Exception | None = None
    total_attempts = retry_count + 1
    for attempt in range(1, total_attempts + 1):
        try:
            return callback()
        except Exception as error:
            last_error = error
            if attempt == total_attempts:
                break
            wait_seconds = max(sleep_seconds, 0.5) * attempt
            print(f"    재시도 {attempt}/{retry_count}: {retry_label} 실패 -> {wait_seconds:.1f}초 후 재시도")
            time.sleep(wait_seconds)

    assert last_error is not None
    raise last_error


def extract_rcept_no(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        rcept_no = clean_text(row.get("rcept_no"))
        if rcept_no:
            return rcept_no
    return None


def download_xbrl_document(api_key: str, output_dir: Path, rcept_no: str, reprt_code: str) -> str:
    import dart_fss as dart
    from dart_fss.api.finance import download_xbrl

    output_dir.mkdir(parents=True, exist_ok=True)
    dart.set_api_key(api_key=api_key)
    return download_xbrl(path=str(output_dir), rcept_no=rcept_no, reprt_code=reprt_code)


def main() -> int:
    args = parse_args()
    years = prompt_for_year_count(args.years)
    api_key = resolved_api_key(args.api_key)
    target_years = completed_business_years(years)
    corp_codes = load_corp_codes(args.corp_codes_file)
    report_codes = resolve_report_codes(args.reports)
    statement_bases = resolve_statement_bases(args.statement_bases)
    scopes = resolve_scopes(args.scopes)

    if "xbrl" in scopes and not ({"statements", "major_accounts"} & set(scopes)):
        raise DatasetError("xbrl scope requires statements or major_accounts so a filing number can be resolved.")

    print(f"[1/5] corp_code 목록 로드 중... count={len(corp_codes)}")
    print("[2/5] DART 기업코드 목록 조회 중...")
    dart_client = DartClient(api_key)
    corp_codes_by_stock = dart_client.fetch_corp_codes()
    corp_codes_by_corp = {
        entry["corp_code"]: CorpCodeEntry(
            corp_code=entry["corp_code"],
            stock_code=entry["stock_code"],
            corp_name=entry["corp_name"],
            modify_date=entry.get("modify_date"),
        )
        for entry in corp_codes_by_stock.values()
    }
    ksic_classifier = KsicClassifier(args.ksic_path)
    ksic_classifier.load()

    database = Database(args.db_path)
    run_id = database.start_run("CUSTOM", len(corp_codes), years)

    try:
        print(f"[3/5] 회사 메타데이터 저장 중... 대상 연도: {target_years}")
        bound_companies: list[CompanyDetails] = []
        skipped_corp_codes: list[str] = []
        for corp_code in corp_codes:
            corp_info = corp_codes_by_corp.get(corp_code)
            if not corp_info:
                skipped_corp_codes.append(corp_code)
                database.record_failure(
                    run_id=run_id,
                    company=None,
                    stage="corp_code_missing",
                    error_message=f"No DART corp_code master entry found for corp_code={corp_code}",
                )
                continue
            try:
                overview = fetch_with_retries(
                    callback=lambda corp_code=corp_code: dart_client.fetch_company_overview(corp_code),
                    retry_count=args.retry_count,
                    sleep_seconds=args.request_sleep,
                    retry_label=f"{corp_info.corp_name} company overview",
                )
            except Exception as error:
                fallback_company = CompanyDetails(
                    corp_code=corp_code,
                    corp_name=corp_info.corp_name,
                    stock_code=corp_info.stock_code,
                    market="UNKNOWN",
                    market_rank=0,
                    market_cap_krw=0,
                    current_price_krw=0,
                    dart_modify_date=corp_info.modify_date,
                    dart_sector_name=None,
                    ksic_macro_sector=None,
                )
                database.record_failure(
                    run_id=run_id,
                    company=fallback_company,
                    stage="company_overview",
                    error_message=str(error),
                )
                overview = {}
            company_details = CompanyDetails(
                corp_code=corp_code,
                corp_name=corp_info.corp_name,
                stock_code=corp_info.stock_code,
                market=market_from_corp_cls(overview.get("corp_cls")),
                market_rank=0,
                market_cap_krw=0,
                current_price_krw=0,
                dart_modify_date=corp_info.modify_date,
                dart_sector_name=clean_text(overview.get("induty_code")),
                ksic_macro_sector=ksic_classifier.classify(overview.get("induty_code")),
            )
            database.upsert_company(company_details)
            bound_companies.append(company_details)

        print("[4/5] 요청 범위 수집 및 저장 중...")
        for company in bound_companies:
            print(f"  - [{company.market}] {company.corp_name} ({company.stock_code}, corp_code={company.corp_code})")
            for year in target_years:
                for report_code in report_codes:
                    report_label = REPORT_CODE_LABELS[report_code]
                    latest_rcept_no: str | None = None

                    if "statements" in scopes:
                        for fs_division in statement_bases:
                            try:
                                status, rows = fetch_with_retries(
                                    callback=lambda corp_code=company.corp_code, year=year, report_code=report_code, fs_division=fs_division:
                                        dart_client.fetch_financial_statements(corp_code, year, report_code, fs_division),
                                    retry_count=args.retry_count,
                                    sleep_seconds=args.request_sleep,
                                    retry_label=f"{company.corp_name} {year} {report_label} {fs_division}",
                                )
                                database.replace_financial_rows(
                                    corp_code=company.corp_code,
                                    stock_code=company.stock_code,
                                    corp_name=company.corp_name,
                                    year=year,
                                    reprt_code=report_code,
                                    fs_division=fs_division,
                                    rows=rows,
                                    source_status=status,
                                )
                                latest_rcept_no = latest_rcept_no or extract_rcept_no(rows)
                            except Exception as error:
                                database.record_failure(
                                    run_id=run_id,
                                    company=company,
                                    business_year=year,
                                    fs_division=fs_division,
                                    stage="financial_fetch",
                                    error_message=str(error),
                                )
                            time.sleep(args.request_sleep)

                    if "major_accounts" in scopes:
                        try:
                            status, rows = fetch_with_retries(
                                callback=lambda corp_code=company.corp_code, year=year, report_code=report_code:
                                    dart_client.fetch_major_accounts(corp_code, year, report_code),
                                retry_count=args.retry_count,
                                sleep_seconds=args.request_sleep,
                                retry_label=f"{company.corp_name} {year} {report_label} major_accounts",
                            )
                            database.replace_major_account_rows(
                                corp_code=company.corp_code,
                                stock_code=company.stock_code,
                                corp_name=company.corp_name,
                                year=year,
                                reprt_code=report_code,
                                rows=rows,
                                source_status=status,
                            )
                            latest_rcept_no = latest_rcept_no or extract_rcept_no(rows)
                        except Exception as error:
                            database.record_failure(
                                run_id=run_id,
                                company=company,
                                business_year=year,
                                stage="major_account_fetch",
                                error_message=str(error),
                            )
                        time.sleep(args.request_sleep)

                    if "xbrl" in scopes:
                        if not latest_rcept_no:
                            database.record_failure(
                                run_id=run_id,
                                company=company,
                                business_year=year,
                                stage="xbrl_download",
                                error_message=f"Could not resolve rcept_no for {report_code}",
                            )
                            continue
                        try:
                            local_path = fetch_with_retries(
                                callback=lambda api_key=api_key, output_dir=args.xbrl_dir / company.corp_code / str(year) / report_code, rcept_no=latest_rcept_no, reprt_code=report_code:
                                    download_xbrl_document(api_key, output_dir, rcept_no, reprt_code),
                                retry_count=args.retry_count,
                                sleep_seconds=args.request_sleep,
                                retry_label=f"{company.corp_name} {year} {report_label} xbrl",
                            )
                            database.upsert_xbrl_document(
                                XbrlDocument(
                                    corp_code=company.corp_code,
                                    stock_code=company.stock_code,
                                    corp_name=company.corp_name,
                                    bsns_year=str(year),
                                    reprt_code=report_code,
                                    rcept_no=latest_rcept_no,
                                    local_path=local_path,
                                    fetched_at=utc_now(),
                                )
                            )
                        except Exception as error:
                            database.record_failure(
                                run_id=run_id,
                                company=company,
                                business_year=year,
                                stage="xbrl_download",
                                error_message=str(error),
                            )
                        time.sleep(args.request_sleep)

        exported_files: list[Path] = []
        if not args.skip_export:
            print("[5/5] 기업별 CSV export 생성 중...")
            exported_files = database.export_company_csvs(args.export_dir)
        else:
            print("[5/5] CSV export 단계 생략.")

        database.finish_run(run_id, "success")
        print("\n완료")
        print(f"- SQLite DB: {args.db_path}")
        print(f"- corp_code 입력 수: {len(corp_codes)}")
        print(f"- DART 적재 대상 수: {len(bound_companies)}")
        if skipped_corp_codes:
            print(f"- 미매핑 corp_code 수: {len(skipped_corp_codes)}")
        print(f"- 대상 연도: {target_years}")
        print(f"- 보고서: {[REPORT_CODE_LABELS[code] for code in report_codes]}")
        print(f"- 연결/별도: {statement_bases}")
        print(f"- 수집 범위: {scopes}")
        if exported_files:
            print(f"- CSV export 수: {len(exported_files)}")
        return 0
    except Exception as error:
        database.finish_run(run_id, "failed", str(error))
        raise
    finally:
        database.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
