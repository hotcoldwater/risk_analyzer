from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "dart-data" / "db"
INPUT_CSV = DB_DIR / "financial_statement_accounts.csv"
STANDARDS_DB = DB_DIR / "dart_standards.db"
SUMMARY_CSV = DB_DIR / "account_analysis_summary.csv"
ALIAS_CSV = DB_DIR / "account_alias_candidates.csv"

REQUIRED_COLUMNS = {
    "sj_nm",
    "account_nm",
    "account_id",
    "account_detail",
    "occurrences",
    "company_count",
}

UNMAPPED_ACCOUNT_ID = "-표준계정코드 미사용-"


def require_columns(frame: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")


def clean_account_name(value: object) -> str:
    if pd.isna(value):
        return ""

    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("[", "(").replace("]", ")")
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"[·•ㆍ]", "", text)
    text = re.sub(r"[\"'`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "")
    return text


def load_accounts() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_CSV}")

    frame = pd.read_csv(INPUT_CSV)
    require_columns(frame, REQUIRED_COLUMNS)

    frame["account_nm_clean"] = frame["account_nm"].map(clean_account_name)
    frame["account_id"] = frame["account_id"].fillna("").astype(str)
    frame["account_detail"] = frame["account_detail"].fillna("").astype(str)
    frame["sj_nm"] = frame["sj_nm"].fillna("").astype(str)
    frame["occurrences"] = pd.to_numeric(frame["occurrences"], errors="coerce").fillna(0).astype(int)
    frame["company_count"] = pd.to_numeric(frame["company_count"], errors="coerce").fillna(0).astype(int)
    return frame


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(frame)
    summary_rows: list[dict[str, object]] = [
        {"section": "overall", "sj_nm": "", "metric": "total_rows", "value": total_rows},
        {"section": "overall", "sj_nm": "", "metric": "unique_account_nm", "value": frame["account_nm"].nunique()},
        {
            "section": "overall",
            "sj_nm": "",
            "metric": "unique_account_nm_clean",
            "value": frame["account_nm_clean"].nunique(),
        },
        {"section": "overall", "sj_nm": "", "metric": "unique_account_id", "value": frame["account_id"].nunique()},
    ]

    unused_count = int((frame["account_id"] == UNMAPPED_ACCOUNT_ID).sum())
    unused_ratio = round((unused_count / total_rows) * 100, 2) if total_rows else 0.0
    summary_rows.extend(
        [
            {
                "section": "overall",
                "sj_nm": "",
                "metric": "unused_account_id_rows",
                "value": unused_count,
            },
            {
                "section": "overall",
                "sj_nm": "",
                "metric": "unused_account_id_ratio_pct",
                "value": unused_ratio,
            },
        ]
    )

    statement_stats = (
        frame.groupby("sj_nm", dropna=False)
        .agg(
            row_count=("account_nm", "size"),
            occurrences_sum=("occurrences", "sum"),
            company_count_sum=("company_count", "sum"),
            unique_account_nm=("account_nm", "nunique"),
            unique_account_id=("account_id", "nunique"),
        )
        .reset_index()
        .sort_values(["row_count", "sj_nm"], ascending=[False, True])
    )
    statement_stats["row_ratio_pct"] = (
        (statement_stats["row_count"] / total_rows * 100).round(2) if total_rows else 0.0
    )

    for row in statement_stats.to_dict(orient="records"):
        for metric in (
            "row_count",
            "row_ratio_pct",
            "occurrences_sum",
            "company_count_sum",
            "unique_account_nm",
            "unique_account_id",
        ):
            summary_rows.append(
                {
                    "section": "statement_distribution",
                    "sj_nm": row["sj_nm"],
                    "metric": metric,
                    "value": row[metric],
                }
            )

    return pd.DataFrame(summary_rows), statement_stats


def build_alias_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    usable = frame[
        frame["account_id"].ne("")
        & frame["account_id"].ne(UNMAPPED_ACCOUNT_ID)
    ].copy()
    alias_rows: list[dict[str, object]] = []

    for (sj_nm, account_id), group in usable.groupby(["sj_nm", "account_id"], dropna=False):
        unique_names = sorted(group["account_nm_clean"].dropna().unique().tolist())
        if len(unique_names) < 2:
            continue

        top_names = (
            group.groupby(["account_nm", "account_nm_clean"], dropna=False)["occurrences"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        sample_names = " | ".join(top_names["account_nm"].head(10).tolist())
        alias_rows.append(
            {
                "sj_nm": sj_nm,
                "account_id": account_id,
                "unique_account_nm_count": len(unique_names),
                "total_occurrences": int(group["occurrences"].sum()),
                "total_company_count": int(group["company_count"].sum()),
                "sample_account_names": sample_names,
            }
        )

    alias_frame = pd.DataFrame(alias_rows)
    if alias_frame.empty:
        return pd.DataFrame(
            columns=[
                "sj_nm",
                "account_id",
                "unique_account_nm_count",
                "total_occurrences",
                "total_company_count",
                "sample_account_names",
            ]
        )

    return alias_frame.sort_values(
        ["unique_account_nm_count", "total_occurrences", "sj_nm", "account_id"],
        ascending=[False, False, True, True],
    )


def save_to_sqlite(summary: pd.DataFrame, alias_candidates: pd.DataFrame) -> None:
    with sqlite3.connect(STANDARDS_DB) as connection:
        summary.to_sql("account_analysis_summary", connection, if_exists="replace", index=False)
        alias_candidates.to_sql("account_alias_candidates", connection, if_exists="replace", index=False)


def print_console_summary(frame: pd.DataFrame, statement_stats: pd.DataFrame) -> None:
    total_rows = len(frame)
    unique_raw = frame["account_nm"].nunique()
    unique_clean = frame["account_nm_clean"].nunique()
    unused_count = int((frame["account_id"] == UNMAPPED_ACCOUNT_ID).sum())
    unused_ratio = round((unused_count / total_rows) * 100, 2) if total_rows else 0.0

    print(f"전체 행 수: {total_rows:,}")
    print(f"고유 원본 계정명 수: {unique_raw:,}")
    print(f"고유 정리 계정명 수: {unique_clean:,}")
    print(f"표준계정코드 미사용 비중: {unused_count:,}행 ({unused_ratio:.2f}%)")
    print("재무제표별 행 수:")
    for row in statement_stats.to_dict(orient="records"):
        print(f"  - {row['sj_nm']}: {row['row_count']:,}행 ({row['row_ratio_pct']:.2f}%)")


def main() -> None:
    frame = load_accounts()
    summary, statement_stats = build_summary(frame)
    alias_candidates = build_alias_candidates(frame)

    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    alias_candidates.to_csv(ALIAS_CSV, index=False, encoding="utf-8-sig")
    save_to_sqlite(summary, alias_candidates)
    print_console_summary(frame, statement_stats)
    print(f"저장 완료: {SUMMARY_CSV}")
    print(f"저장 완료: {ALIAS_CSV}")
    print(f"SQLite 반영 완료: {STANDARDS_DB}")


if __name__ == "__main__":
    main()
