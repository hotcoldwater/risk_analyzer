from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "dart-data" / "db"
INPUT_CSV = DB_DIR / "financial_statement_accounts.csv"
STANDARDS_DB = DB_DIR / "dart_standards.db"
MAPPING_CSV = DB_DIR / "account_standard_mapping.csv"

REQUIRED_COLUMNS = {
    "sj_nm",
    "account_nm",
    "account_id",
    "account_detail",
    "occurrences",
    "company_count",
}

UNMAPPED_ACCOUNT_ID = "-표준계정코드 미사용-"
NEEDS_REVIEW_PATTERNS = (
    "기타",
    "합계",
    "조정",
    "기타변동",
    "기타수익",
    "기타비용",
    "기타자산",
    "기타부채",
)

STATEMENT_PRIORITY = {
    "재무상태표": 1,
    "손익계산서": 2,
    "포괄손익계산서": 2,
    "현금흐름표": 3,
    "자본변동표": 4,
}

ACCOUNT_ID_EXACT_MAP = {
    ("재무상태표", "ifrs-full_Assets"): ("BS_ASSETS_TOTAL", "자산총계", "total_assets"),
    ("재무상태표", "ifrs-full_Liabilities"): ("BS_LIABILITIES_TOTAL", "부채총계", "total_liabilities"),
    ("재무상태표", "ifrs-full_Equity"): ("BS_EQUITY_TOTAL", "자본총계", "total_equity"),
    ("재무상태표", "ifrs-full_CashAndCashEquivalents"): ("BS_CASH", "현금및현금성자산", "cash"),
    ("재무상태표", "ifrs-full_TradeAndOtherCurrentReceivables"): ("BS_RECEIVABLES", "매출채권", "receivables"),
    ("재무상태표", "dart_ReceivablesTradeCurrent"): ("BS_RECEIVABLES", "매출채권", "receivables"),
    ("재무상태표", "ifrs-full_Inventories"): ("BS_INVENTORIES", "재고자산", "inventory"),
    ("손익계산서", "ifrs-full_Revenue"): ("IS_REVENUE", "매출액", "revenue"),
    ("포괄손익계산서", "ifrs-full_Revenue"): ("IS_REVENUE", "매출액", "revenue"),
    ("손익계산서", "ifrs-full_CostOfSales"): ("IS_COGS", "매출원가", "cost_of_sales"),
    ("포괄손익계산서", "ifrs-full_CostOfSales"): ("IS_COGS", "매출원가", "cost_of_sales"),
    ("손익계산서", "ifrs-full_GrossProfit"): ("IS_GROSS_PROFIT", "매출총이익", "gross_profit"),
    ("포괄손익계산서", "ifrs-full_GrossProfit"): ("IS_GROSS_PROFIT", "매출총이익", "gross_profit"),
    ("손익계산서", "dart_OperatingIncomeLoss"): ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income"),
    ("포괄손익계산서", "dart_OperatingIncomeLoss"): ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income"),
    ("손익계산서", "ifrs-full_ProfitLossBeforeTax"): (
        "IS_PROFIT_BEFORE_TAX",
        "법인세비용차감전순이익(손실)",
        "profit_before_tax",
    ),
    ("포괄손익계산서", "ifrs-full_ProfitLossBeforeTax"): (
        "IS_PROFIT_BEFORE_TAX",
        "법인세비용차감전순이익(손실)",
        "profit_before_tax",
    ),
    ("손익계산서", "ifrs-full_ProfitLoss"): ("IS_NET_INCOME", "당기순이익(손실)", "net_income"),
    ("포괄손익계산서", "ifrs-full_ProfitLoss"): ("IS_NET_INCOME", "당기순이익(손실)", "net_income"),
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInOperatingActivities"): (
        "CF_OPERATING",
        "영업활동현금흐름",
        "operating_cash_flow",
    ),
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInInvestingActivities"): (
        "CF_INVESTING",
        "투자활동현금흐름",
        "investing_cash_flow",
    ),
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInFinancingActivities"): (
        "CF_FINANCING",
        "재무활동현금흐름",
        "financing_cash_flow",
    ),
}

NAME_RULE_MAP = {
    "재무상태표": {
        "총자산": ("BS_ASSETS_TOTAL", "자산총계", "total_assets", 90),
        "자산총계": ("BS_ASSETS_TOTAL", "자산총계", "total_assets", 90),
        "총부채": ("BS_LIABILITIES_TOTAL", "부채총계", "total_liabilities", 90),
        "부채총계": ("BS_LIABILITIES_TOTAL", "부채총계", "total_liabilities", 90),
        "순자산": ("BS_EQUITY_TOTAL", "자본총계", "total_equity", 80),
        "자본총계": ("BS_EQUITY_TOTAL", "자본총계", "total_equity", 90),
        "현금및현금성자산": ("BS_CASH", "현금및현금성자산", "cash", 85),
        "매출채권": ("BS_RECEIVABLES", "매출채권", "receivables", 85),
        "재고자산": ("BS_INVENTORIES", "재고자산", "inventory", 85),
    },
    "손익계산서": {
        "매출": ("IS_REVENUE", "매출액", "revenue", 85),
        "매출액": ("IS_REVENUE", "매출액", "revenue", 90),
        "수익": ("IS_REVENUE", "매출액", "revenue", 75),
        "영업수익": ("IS_REVENUE", "매출액", "revenue", 80),
        "매출원가": ("IS_COGS", "매출원가", "cost_of_sales", 90),
        "매출총이익": ("IS_GROSS_PROFIT", "매출총이익", "gross_profit", 90),
        "영업손익": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 85),
        "영업이익": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 90),
        "영업이익(손실)": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 90),
        "영업이익손실": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 85),
        "법인세비용차감전순이익": (
            "IS_PROFIT_BEFORE_TAX",
            "법인세비용차감전순이익(손실)",
            "profit_before_tax",
            90,
        ),
        "법인세비용차감전순이익(손실)": (
            "IS_PROFIT_BEFORE_TAX",
            "법인세비용차감전순이익(손실)",
            "profit_before_tax",
            90,
        ),
        "당기순이익": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 90),
        "당기순손실": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 85),
        "당기순손익": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 85),
        "당기순이익(손실)": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 90),
    },
    "포괄손익계산서": {
        "매출": ("IS_REVENUE", "매출액", "revenue", 85),
        "매출액": ("IS_REVENUE", "매출액", "revenue", 90),
        "수익": ("IS_REVENUE", "매출액", "revenue", 75),
        "영업수익": ("IS_REVENUE", "매출액", "revenue", 80),
        "매출원가": ("IS_COGS", "매출원가", "cost_of_sales", 90),
        "매출총이익": ("IS_GROSS_PROFIT", "매출총이익", "gross_profit", 90),
        "영업손익": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 85),
        "영업이익": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 90),
        "영업이익(손실)": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 90),
        "영업이익손실": ("IS_OPERATING_INCOME", "영업이익(손실)", "operating_income", 85),
        "법인세비용차감전순이익": (
            "IS_PROFIT_BEFORE_TAX",
            "법인세비용차감전순이익(손실)",
            "profit_before_tax",
            90,
        ),
        "법인세비용차감전순이익(손실)": (
            "IS_PROFIT_BEFORE_TAX",
            "법인세비용차감전순이익(손실)",
            "profit_before_tax",
            90,
        ),
        "당기순이익": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 90),
        "당기순손실": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 85),
        "당기순손익": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 85),
        "당기순이익(손실)": ("IS_NET_INCOME", "당기순이익(손실)", "net_income", 90),
    },
    "현금흐름표": {
        "영업활동현금흐름": ("CF_OPERATING", "영업활동현금흐름", "operating_cash_flow", 90),
        "영업활동으로인한현금흐름": ("CF_OPERATING", "영업활동현금흐름", "operating_cash_flow", 85),
        "투자활동현금흐름": ("CF_INVESTING", "투자활동현금흐름", "investing_cash_flow", 90),
        "투자활동으로인한현금흐름": ("CF_INVESTING", "투자활동현금흐름", "investing_cash_flow", 85),
        "재무활동현금흐름": ("CF_FINANCING", "재무활동현금흐름", "financing_cash_flow", 90),
        "재무활동으로인한현금흐름": ("CF_FINANCING", "재무활동현금흐름", "financing_cash_flow", 85),
        "현금및현금성자산의증가감소": ("CF_CASH_INCREASE", "현금및현금성자산의증가감소", "cash_change", 90),
        "현금및현금성자산의순증감": ("CF_CASH_INCREASE", "현금및현금성자산의증가감소", "cash_change", 85),
        "현금및현금성자산의순증가(감소)": (
            "CF_CASH_INCREASE",
            "현금및현금성자산의증가감소",
            "cash_change",
            85,
        ),
    },
}


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
    return frame


def preserve_raw_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["account_nm_raw"] = normalized["account_nm"].fillna("").astype(str)
    normalized["account_id_raw"] = normalized["account_id"].fillna("").astype(str)
    normalized["account_detail_raw"] = normalized["account_detail"].fillna("").astype(str)
    normalized["sj_nm"] = normalized["sj_nm"].fillna("").astype(str)
    normalized["occurrences"] = pd.to_numeric(normalized["occurrences"], errors="coerce").fillna(0).astype(int)
    normalized["company_count"] = pd.to_numeric(normalized["company_count"], errors="coerce").fillna(0).astype(int)
    normalized["account_nm_clean"] = normalized["account_nm_raw"].map(clean_account_name)
    normalized["raw_account_nm_clean"] = normalized["account_nm_clean"]
    normalized["raw_account_id"] = normalized["account_id_raw"]
    normalized["statement_type"] = normalized["sj_nm"]
    normalized["priority"] = normalized["statement_type"].map(STATEMENT_PRIORITY).fillna(99).astype(int)
    normalized["standard_account_id"] = pd.NA
    normalized["standard_account_nm"] = pd.NA
    normalized["account_bucket"] = pd.NA
    normalized["confidence"] = 0
    normalized["mapping_rule"] = "needs_review"
    normalized["memo"] = ""
    return normalized


def is_needs_review_name(account_nm_clean: str) -> bool:
    return any(pattern in account_nm_clean for pattern in NEEDS_REVIEW_PATTERNS)


def assign_mapping(
    frame: pd.DataFrame,
    mask: pd.Series,
    standard_id: str,
    standard_name: str,
    bucket: str,
    confidence: int,
    mapping_rule: str,
    memo: str = "",
) -> None:
    frame.loc[mask, "standard_account_id"] = standard_id
    frame.loc[mask, "standard_account_nm"] = standard_name
    frame.loc[mask, "account_bucket"] = bucket
    frame.loc[mask, "confidence"] = confidence
    frame.loc[mask, "mapping_rule"] = mapping_rule
    frame.loc[mask, "memo"] = memo


def apply_review_holds(frame: pd.DataFrame) -> None:
    mask = frame["account_nm_clean"].map(is_needs_review_name)
    frame.loc[mask, "standard_account_id"] = pd.NA
    frame.loc[mask, "standard_account_nm"] = pd.NA
    frame.loc[mask, "account_bucket"] = pd.NA
    frame.loc[mask, "confidence"] = 0
    frame.loc[mask, "mapping_rule"] = "needs_review"
    frame.loc[mask, "memo"] = "자동 매핑 제외: 의미 불명확"


def apply_account_id_mappings(frame: pd.DataFrame) -> None:
    for (statement_type, raw_account_id), (standard_id, standard_name, bucket) in ACCOUNT_ID_EXACT_MAP.items():
        mask = (
            frame["statement_type"].eq(statement_type)
            & frame["account_id_raw"].eq(raw_account_id)
            & frame["standard_account_id"].isna()
        )
        assign_mapping(frame, mask, standard_id, standard_name, bucket, 100, "account_id_exact")


def apply_name_rule_mappings(frame: pd.DataFrame) -> None:
    for statement_type, mappings in NAME_RULE_MAP.items():
        statement_mask = (
            frame["statement_type"].eq(statement_type)
            & frame["account_id_raw"].eq(UNMAPPED_ACCOUNT_ID)
            & frame["standard_account_id"].isna()
        )
        for clean_name, (standard_id, standard_name, bucket, confidence) in mappings.items():
            mask = statement_mask & frame["account_nm_clean"].eq(clean_name)
            assign_mapping(frame, mask, standard_id, standard_name, bucket, confidence, "account_name_rule")


def finalize_review_flags(frame: pd.DataFrame) -> None:
    unresolved = frame["standard_account_id"].isna()
    frame.loc[unresolved & frame["memo"].eq(""), "memo"] = "검토 필요"
    frame.loc[frame["standard_account_id"].isna(), "mapping_rule"] = "needs_review"


def validate_core_accounts(frame: pd.DataFrame) -> pd.DataFrame:
    core_ids = {
        "BS_ASSETS_TOTAL": "자산총계",
        "BS_LIABILITIES_TOTAL": "부채총계",
        "BS_EQUITY_TOTAL": "자본총계",
    }
    validation_rows: list[dict[str, object]] = []

    for standard_id, standard_name in core_ids.items():
        subset = frame[frame["standard_account_id"].eq(standard_id)]
        validation_rows.append(
            {
                "standard_account_id": standard_id,
                "standard_account_nm": standard_name,
                "matched_rows": int(len(subset)),
                "matched_occurrences": int(subset["occurrences"].sum()),
                "matched_company_count": int(subset["company_count"].sum()),
                "is_valid": bool(len(subset) > 0),
            }
        )

    validation = pd.DataFrame(validation_rows)
    if not validation["is_valid"].all():
        missing = validation.loc[~validation["is_valid"], "standard_account_nm"].tolist()
        raise ValueError(f"핵심 계정 매핑 검증 실패: {', '.join(missing)}")
    return validation


def build_output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ordered_columns = [
        "sj_nm",
        "statement_type",
        "raw_account_id",
        "account_nm_raw",
        "account_nm_clean",
        "raw_account_nm_clean",
        "account_id_raw",
        "account_detail_raw",
        "standard_account_id",
        "standard_account_nm",
        "account_bucket",
        "priority",
        "confidence",
        "mapping_rule",
        "memo",
        "occurrences",
        "company_count",
    ]
    return frame[ordered_columns].sort_values(
        ["priority", "sj_nm", "standard_account_id", "account_id_raw", "account_nm_clean", "account_detail_raw"],
        na_position="last",
    )


def save_to_sqlite(mapping_frame: pd.DataFrame, validation_frame: pd.DataFrame) -> None:
    with sqlite3.connect(STANDARDS_DB) as connection:
        mapping_frame.to_sql("account_standard_mapping", connection, if_exists="replace", index=False)
        validation_frame.to_sql("account_core_validation", connection, if_exists="replace", index=False)


def print_console_summary(mapping_frame: pd.DataFrame, validation_frame: pd.DataFrame) -> None:
    total_rows = len(mapping_frame)
    unique_raw = mapping_frame["account_nm_raw"].nunique()
    unique_clean = mapping_frame["account_nm_clean"].nunique()
    unused_count = int((mapping_frame["account_id_raw"] == UNMAPPED_ACCOUNT_ID).sum())
    unused_ratio = round((unused_count / total_rows) * 100, 2) if total_rows else 0.0
    auto_mapped = int(mapping_frame["standard_account_id"].notna().sum())
    needs_review = int(mapping_frame["standard_account_id"].isna().sum())

    print(f"전체 행 수: {total_rows:,}")
    print(f"고유 원본 계정명 수: {unique_raw:,}")
    print(f"고유 정리 계정명 수: {unique_clean:,}")
    print(f"표준계정코드 미사용 비중: {unused_count:,}행 ({unused_ratio:.2f}%)")
    print("재무제표별 행 수:")
    for sj_nm, count in mapping_frame.groupby("sj_nm").size().sort_values(ascending=False).items():
        print(f"  - {sj_nm}: {count:,}행")
    print(f"자동 매핑된 행 수: {auto_mapped:,}")
    print(f"검토 필요 행 수: {needs_review:,}")
    print("핵심 계정별 매핑 결과:")
    for row in validation_frame.to_dict(orient="records"):
        print(
            f"  - {row['standard_account_nm']} ({row['standard_account_id']}): "
            f"{row['matched_rows']:,}행 / {row['matched_company_count']:,}기업"
        )


def main() -> None:
    frame = load_accounts()
    normalized = preserve_raw_columns(frame)
    apply_review_holds(normalized)
    apply_account_id_mappings(normalized)
    apply_name_rule_mappings(normalized)
    finalize_review_flags(normalized)
    validation_frame = validate_core_accounts(normalized)
    output_frame = build_output_columns(normalized)

    output_frame.to_csv(MAPPING_CSV, index=False, encoding="utf-8-sig")
    save_to_sqlite(output_frame, validation_frame)
    print_console_summary(output_frame, validation_frame)
    print(f"저장 완료: {MAPPING_CSV}")
    print(f"SQLite 반영 완료: {STANDARDS_DB}")


if __name__ == "__main__":
    main()
