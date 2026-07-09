from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "kospi"
STANDARDS_DIR = PROJECT_ROOT / "data" / "processed" / "standards"
INPUT_CSV = STANDARDS_DIR / "financial_statement_accounts.csv"
RAW_DB = RAW_DIR / "kospi_raw.db"
STANDARDS_DB = STANDARDS_DIR / "dart_standards.db"
MAPPING_CSV = STANDARDS_DIR / "account_standard_mapping.csv"
STANDARD_FINANCIALS_CSV = STANDARDS_DIR / "standard_financials.csv"

REQUIRED_COLUMNS = {
    "sj_nm",
    "account_nm",
    "account_id",
    "account_detail",
    "occurrences",
    "company_count",
}

UNMAPPED_ACCOUNT_ID = "-표준계정코드 미사용-"
UNKNOWN_FS_TYPE = "UNSPECIFIED"

EXACT_REVIEW_NAMES = {
    "기타",
    "합계",
    "조정",
    "기타변동",
    "기타자산",
    "기타부채",
}

STATEMENT_PRIORITY = {
    "재무상태표": 1,
    "손익계산서": 2,
    "포괄손익계산서": 2,
    "현금흐름표": 3,
    "자본변동표": 4,
}

STANDARD_ACCOUNT_DEFINITIONS = {
    "BS_ASSETS_TOTAL": ("재무상태표", "자산총계", "total_assets"),
    "BS_LIABILITIES_TOTAL": ("재무상태표", "부채총계", "total_liabilities"),
    "BS_EQUITY_TOTAL": ("재무상태표", "자본총계", "total_equity"),
    "BS_CURRENT_ASSETS": ("재무상태표", "유동자산", "current_assets"),
    "BS_CURRENT_LIABILITIES": ("재무상태표", "유동부채", "current_liabilities"),
    "BS_CASH": ("재무상태표", "현금및현금성자산", "cash"),
    "BS_RECEIVABLES": ("재무상태표", "매출채권", "receivables"),
    "BS_INVENTORIES": ("재무상태표", "재고자산", "inventory"),
    "BS_CONTRACT_ASSET": ("재무상태표", "계약자산", "contract_assets"),
    "BS_INTANGIBLE_ASSETS": ("재무상태표", "무형자산", "intangible_assets"),
    "BS_DEVELOPMENT_COST": ("재무상태표", "개발비", "development_cost"),
    "BS_PROVISIONS": ("재무상태표", "충당부채", "provisions"),
    "BS_BORROWINGS": ("재무상태표", "차입금", "borrowings"),
    "BS_RETAINED_EARNINGS": ("재무상태표", "이익잉여금", "retained_earnings"),
    "BS_PPE": ("재무상태표", "유형자산", "property_plant_equipment"),
    "IS_REVENUE": ("손익계산서", "매출액", "revenue"),
    "IS_COGS": ("손익계산서", "매출원가", "cost_of_sales"),
    "IS_GROSS_PROFIT": ("손익계산서", "매출총이익", "gross_profit"),
    "IS_OPERATING_INCOME": ("손익계산서", "영업이익(손실)", "operating_income"),
    "IS_PROFIT_BEFORE_TAX": ("손익계산서", "법인세비용차감전순이익(손실)", "profit_before_tax"),
    "IS_NET_INCOME": ("손익계산서", "당기순이익(손실)", "net_income"),
    "IS_OTHER_INCOME": ("손익계산서", "기타수익", "other_income"),
    "IS_OTHER_EXPENSE": ("손익계산서", "기타비용", "other_expense"),
    "IS_FINANCE_COST": ("손익계산서", "금융비용", "finance_cost"),
    "IS_SGA": ("손익계산서", "판매비와관리비", "selling_general_admin"),
    "IS_DEPRECIATION": ("손익계산서", "감가상각비", "depreciation"),
    "CF_OPERATING": ("현금흐름표", "영업활동현금흐름", "operating_cash_flow"),
    "CF_INVESTING": ("현금흐름표", "투자활동현금흐름", "investing_cash_flow"),
    "CF_FINANCING": ("현금흐름표", "재무활동현금흐름", "financing_cash_flow"),
    "CF_CASH_CHANGE": ("현금흐름표", "현금및현금성자산의증가감소", "cash_change"),
}

ACCOUNT_ID_EXACT_MAP = {
    ("재무상태표", "ifrs-full_Assets"): "BS_ASSETS_TOTAL",
    ("재무상태표", "ifrs-full_Liabilities"): "BS_LIABILITIES_TOTAL",
    ("재무상태표", "ifrs-full_Equity"): "BS_EQUITY_TOTAL",
    ("재무상태표", "ifrs-full_CurrentAssets"): "BS_CURRENT_ASSETS",
    ("재무상태표", "ifrs-full_CurrentLiabilities"): "BS_CURRENT_LIABILITIES",
    ("재무상태표", "ifrs-full_CashAndCashEquivalents"): "BS_CASH",
    ("재무상태표", "ifrs-full_TradeAndOtherCurrentReceivables"): "BS_RECEIVABLES",
    ("재무상태표", "dart_ReceivablesTradeCurrent"): "BS_RECEIVABLES",
    ("재무상태표", "ifrs-full_Inventories"): "BS_INVENTORIES",
    ("재무상태표", "dart_ContractAssetCurrent"): "BS_CONTRACT_ASSET",
    ("재무상태표", "ifrs-full_ContractWithCustomerAssetCurrent"): "BS_CONTRACT_ASSET",
    ("재무상태표", "ifrs-full_IntangibleAssetsOtherThanGoodwill"): "BS_INTANGIBLE_ASSETS",
    ("재무상태표", "dart_DevelopmentCosts"): "BS_DEVELOPMENT_COST",
    ("재무상태표", "ifrs-full_DevelopmentCosts"): "BS_DEVELOPMENT_COST",
    ("재무상태표", "ifrs-full_Provisions"): "BS_PROVISIONS",
    ("재무상태표", "ifrs-full_Borrowings"): "BS_BORROWINGS",
    ("재무상태표", "ifrs-full_RetainedEarnings"): "BS_RETAINED_EARNINGS",
    ("재무상태표", "ifrs-full_PropertyPlantAndEquipment"): "BS_PPE",
    ("손익계산서", "ifrs-full_Revenue"): "IS_REVENUE",
    ("포괄손익계산서", "ifrs-full_Revenue"): "IS_REVENUE",
    ("손익계산서", "ifrs-full_CostOfSales"): "IS_COGS",
    ("포괄손익계산서", "ifrs-full_CostOfSales"): "IS_COGS",
    ("손익계산서", "ifrs-full_GrossProfit"): "IS_GROSS_PROFIT",
    ("포괄손익계산서", "ifrs-full_GrossProfit"): "IS_GROSS_PROFIT",
    ("손익계산서", "dart_OperatingIncomeLoss"): "IS_OPERATING_INCOME",
    ("포괄손익계산서", "dart_OperatingIncomeLoss"): "IS_OPERATING_INCOME",
    ("손익계산서", "ifrs-full_ProfitLossBeforeTax"): "IS_PROFIT_BEFORE_TAX",
    ("포괄손익계산서", "ifrs-full_ProfitLossBeforeTax"): "IS_PROFIT_BEFORE_TAX",
    ("손익계산서", "ifrs-full_ProfitLoss"): "IS_NET_INCOME",
    ("포괄손익계산서", "ifrs-full_ProfitLoss"): "IS_NET_INCOME",
    ("손익계산서", "ifrs-full_OtherGains"): "IS_OTHER_INCOME",
    ("포괄손익계산서", "ifrs-full_OtherGains"): "IS_OTHER_INCOME",
    ("손익계산서", "ifrs-full_OtherLosses"): "IS_OTHER_EXPENSE",
    ("포괄손익계산서", "ifrs-full_OtherLosses"): "IS_OTHER_EXPENSE",
    ("손익계산서", "ifrs-full_FinanceCosts"): "IS_FINANCE_COST",
    ("포괄손익계산서", "ifrs-full_FinanceCosts"): "IS_FINANCE_COST",
    ("손익계산서", "ifrs-full_SellingGeneralAndAdministrativeExpense"): "IS_SGA",
    ("포괄손익계산서", "ifrs-full_SellingGeneralAndAdministrativeExpense"): "IS_SGA",
    ("손익계산서", "ifrs-full_DepreciationExpense"): "IS_DEPRECIATION",
    ("손익계산서", "ifrs-full_DepreciationAndAmortisationExpense"): "IS_DEPRECIATION",
    ("포괄손익계산서", "ifrs-full_DepreciationExpense"): "IS_DEPRECIATION",
    ("포괄손익계산서", "ifrs-full_DepreciationAndAmortisationExpense"): "IS_DEPRECIATION",
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInOperatingActivities"): "CF_OPERATING",
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInInvestingActivities"): "CF_INVESTING",
    ("현금흐름표", "ifrs-full_CashFlowsFromUsedInFinancingActivities"): "CF_FINANCING",
}

NAME_RULE_MAP = {
    "재무상태표": {
        "총자산": ("BS_ASSETS_TOTAL", 90),
        "자산총계": ("BS_ASSETS_TOTAL", 90),
        "총부채": ("BS_LIABILITIES_TOTAL", 90),
        "부채총계": ("BS_LIABILITIES_TOTAL", 90),
        "순자산": ("BS_EQUITY_TOTAL", 80),
        "자본총계": ("BS_EQUITY_TOTAL", 90),
        "현금및현금성자산": ("BS_CASH", 90),
        "유동자산": ("BS_CURRENT_ASSETS", 90),
        "유동부채": ("BS_CURRENT_LIABILITIES", 90),
        "매출채권": ("BS_RECEIVABLES", 90),
        "매출채권및기타채권": ("BS_RECEIVABLES", 80),
        "재고자산": ("BS_INVENTORIES", 90),
        "계약자산": ("BS_CONTRACT_ASSET", 90),
        "무형자산": ("BS_INTANGIBLE_ASSETS", 90),
        "개발비": ("BS_DEVELOPMENT_COST", 90),
        "충당부채": ("BS_PROVISIONS", 90),
        "차입금": ("BS_BORROWINGS", 85),
        "단기차입금": ("BS_BORROWINGS", 80),
        "장기차입금": ("BS_BORROWINGS", 80),
        "이익잉여금": ("BS_RETAINED_EARNINGS", 90),
        "이익잉여금(결손금)": ("BS_RETAINED_EARNINGS", 85),
        "유형자산": ("BS_PPE", 90),
    },
    "손익계산서": {
        "매출": ("IS_REVENUE", 85),
        "매출액": ("IS_REVENUE", 90),
        "수익": ("IS_REVENUE", 75),
        "수익(매출액)": ("IS_REVENUE", 90),
        "영업수익": ("IS_REVENUE", 80),
        "매출원가": ("IS_COGS", 90),
        "매출총이익": ("IS_GROSS_PROFIT", 90),
        "매출총이익(손실)": ("IS_GROSS_PROFIT", 85),
        "영업손익": ("IS_OPERATING_INCOME", 85),
        "영업이익": ("IS_OPERATING_INCOME", 90),
        "영업이익(손실)": ("IS_OPERATING_INCOME", 90),
        "영업이익손실": ("IS_OPERATING_INCOME", 85),
        "법인세비용차감전순이익": ("IS_PROFIT_BEFORE_TAX", 90),
        "법인세비용차감전순이익(손실)": ("IS_PROFIT_BEFORE_TAX", 90),
        "당기순이익": ("IS_NET_INCOME", 90),
        "당기순손실": ("IS_NET_INCOME", 85),
        "당기순손익": ("IS_NET_INCOME", 85),
        "당기순이익(손실)": ("IS_NET_INCOME", 90),
        "기타수익": ("IS_OTHER_INCOME", 90),
        "기타이익": ("IS_OTHER_INCOME", 85),
        "기타비용": ("IS_OTHER_EXPENSE", 90),
        "기타손실": ("IS_OTHER_EXPENSE", 85),
        "금융비용": ("IS_FINANCE_COST", 90),
        "금융원가": ("IS_FINANCE_COST", 80),
        "판매비와관리비": ("IS_SGA", 90),
        "영업비용": ("IS_SGA", 75),
        "감가상각비": ("IS_DEPRECIATION", 90),
        "감가상각비와무형자산상각비": ("IS_DEPRECIATION", 80),
    },
    "포괄손익계산서": {
        "매출": ("IS_REVENUE", 85),
        "매출액": ("IS_REVENUE", 90),
        "수익": ("IS_REVENUE", 75),
        "수익(매출액)": ("IS_REVENUE", 90),
        "영업수익": ("IS_REVENUE", 80),
        "매출원가": ("IS_COGS", 90),
        "매출총이익": ("IS_GROSS_PROFIT", 90),
        "매출총이익(손실)": ("IS_GROSS_PROFIT", 85),
        "영업손익": ("IS_OPERATING_INCOME", 85),
        "영업이익": ("IS_OPERATING_INCOME", 90),
        "영업이익(손실)": ("IS_OPERATING_INCOME", 90),
        "영업이익손실": ("IS_OPERATING_INCOME", 85),
        "법인세비용차감전순이익": ("IS_PROFIT_BEFORE_TAX", 90),
        "법인세비용차감전순이익(손실)": ("IS_PROFIT_BEFORE_TAX", 90),
        "당기순이익": ("IS_NET_INCOME", 90),
        "당기순손실": ("IS_NET_INCOME", 85),
        "당기순손익": ("IS_NET_INCOME", 85),
        "당기순이익(손실)": ("IS_NET_INCOME", 90),
        "기타수익": ("IS_OTHER_INCOME", 90),
        "기타이익": ("IS_OTHER_INCOME", 85),
        "기타비용": ("IS_OTHER_EXPENSE", 90),
        "기타손실": ("IS_OTHER_EXPENSE", 85),
        "금융비용": ("IS_FINANCE_COST", 90),
        "금융원가": ("IS_FINANCE_COST", 80),
        "판매비와관리비": ("IS_SGA", 90),
        "영업비용": ("IS_SGA", 75),
        "감가상각비": ("IS_DEPRECIATION", 90),
        "감가상각비와무형자산상각비": ("IS_DEPRECIATION", 80),
    },
    "현금흐름표": {
        "영업활동현금흐름": ("CF_OPERATING", 90),
        "영업활동으로인한현금흐름": ("CF_OPERATING", 85),
        "영업활동현금흐름(간접법)": ("CF_OPERATING", 80),
        "투자활동현금흐름": ("CF_INVESTING", 90),
        "투자활동으로인한현금흐름": ("CF_INVESTING", 85),
        "재무활동현금흐름": ("CF_FINANCING", 90),
        "재무활동으로인한현금흐름": ("CF_FINANCING", 85),
        "현금및현금성자산의증가감소": ("CF_CASH_CHANGE", 90),
        "현금및현금성자산의증가(감소)": ("CF_CASH_CHANGE", 90),
        "현금및현금성자산의순증감": ("CF_CASH_CHANGE", 85),
        "현금및현금성자산의순증가(감소)": ("CF_CASH_CHANGE", 85),
    },
}

KEYWORD_RULE_MAP = {
    "재무상태표": [
        ("계약자산", "BS_CONTRACT_ASSET", 75),
        ("충당부채", "BS_PROVISIONS", 75),
        ("차입금", "BS_BORROWINGS", 70),
        ("개발비", "BS_DEVELOPMENT_COST", 75),
    ],
    "손익계산서": [
        ("감가상각비", "IS_DEPRECIATION", 75),
        ("금융비용", "IS_FINANCE_COST", 75),
        ("판매비와관리비", "IS_SGA", 75),
    ],
    "포괄손익계산서": [
        ("감가상각비", "IS_DEPRECIATION", 75),
        ("금융비용", "IS_FINANCE_COST", 75),
        ("판매비와관리비", "IS_SGA", 75),
    ],
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
    return text.replace(" ", "")


def parse_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", ""}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = text.replace(",", "").replace("(", "").replace(")", "").replace(" ", "")
    if not text:
        return None

    try:
        amount = float(text)
    except ValueError:
        return None
    return -amount if negative else amount


def standard_meta(standard_id: str) -> tuple[str, str, str]:
    return STANDARD_ACCOUNT_DEFINITIONS[standard_id]


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


def is_review_hold_name(account_nm_clean: str) -> bool:
    return account_nm_clean in EXACT_REVIEW_NAMES


def assign_mapping(
    frame: pd.DataFrame,
    mask: pd.Series,
    standard_id: str,
    confidence: int,
    mapping_rule: str,
    memo: str = "",
) -> None:
    _, standard_name, bucket = standard_meta(standard_id)
    frame.loc[mask, "standard_account_id"] = standard_id
    frame.loc[mask, "standard_account_nm"] = standard_name
    frame.loc[mask, "account_bucket"] = bucket
    frame.loc[mask, "confidence"] = confidence
    frame.loc[mask, "mapping_rule"] = mapping_rule
    frame.loc[mask, "memo"] = memo


def apply_review_holds(frame: pd.DataFrame) -> None:
    mask = frame["account_nm_clean"].map(is_review_hold_name)
    frame.loc[mask, "standard_account_id"] = pd.NA
    frame.loc[mask, "standard_account_nm"] = pd.NA
    frame.loc[mask, "account_bucket"] = pd.NA
    frame.loc[mask, "confidence"] = 0
    frame.loc[mask, "mapping_rule"] = "needs_review"
    frame.loc[mask, "memo"] = "자동 매핑 제외: 의미 불명확"


def apply_account_id_mappings(frame: pd.DataFrame) -> None:
    for (statement_type, raw_account_id), standard_id in ACCOUNT_ID_EXACT_MAP.items():
        mask = (
            frame["statement_type"].eq(statement_type)
            & frame["account_id_raw"].eq(raw_account_id)
            & frame["standard_account_id"].isna()
        )
        assign_mapping(frame, mask, standard_id, 100, "account_id_exact")


def apply_name_rule_mappings(frame: pd.DataFrame, include_any_account_id: bool) -> None:
    rule_name = "account_name_rule" if not include_any_account_id else "account_name_fallback"
    for statement_type, mappings in NAME_RULE_MAP.items():
        statement_mask = frame["statement_type"].eq(statement_type) & frame["standard_account_id"].isna()
        if not include_any_account_id:
            statement_mask &= frame["account_id_raw"].eq(UNMAPPED_ACCOUNT_ID)
        for clean_name, (standard_id, confidence) in mappings.items():
            mask = statement_mask & frame["account_nm_clean"].eq(clean_name)
            assign_mapping(frame, mask, standard_id, confidence, rule_name)


def apply_keyword_rule_mappings(frame: pd.DataFrame) -> None:
    for statement_type, rules in KEYWORD_RULE_MAP.items():
        statement_mask = frame["statement_type"].eq(statement_type) & frame["standard_account_id"].isna()
        for keyword, standard_id, confidence in rules:
            mask = statement_mask & frame["account_nm_clean"].str.contains(keyword, regex=False)
            assign_mapping(frame, mask, standard_id, confidence, "account_keyword_rule")


def finalize_review_flags(frame: pd.DataFrame) -> None:
    unresolved = frame["standard_account_id"].isna()
    frame.loc[unresolved & frame["memo"].eq(""), "memo"] = "검토 필요"
    frame.loc[frame["standard_account_id"].isna(), "mapping_rule"] = "needs_review"


def validate_core_accounts(frame: pd.DataFrame) -> pd.DataFrame:
    core_ids = (
        "BS_ASSETS_TOTAL",
        "BS_LIABILITIES_TOTAL",
        "BS_EQUITY_TOTAL",
        "IS_REVENUE",
        "IS_OPERATING_INCOME",
        "IS_NET_INCOME",
        "CF_OPERATING",
    )
    validation_rows: list[dict[str, object]] = []

    for standard_id in core_ids:
        _, standard_name, _ = standard_meta(standard_id)
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


def build_standard_account_dictionary(mapping_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for standard_id, (statement_type, standard_name, bucket) in STANDARD_ACCOUNT_DEFINITIONS.items():
        matched = mapping_frame[mapping_frame["standard_account_id"].eq(standard_id)]
        rows.append(
            {
                "standard_account_id": standard_id,
                "statement_type": statement_type,
                "standard_account_nm": standard_name,
                "account_bucket": bucket,
                "priority": STATEMENT_PRIORITY.get(statement_type, 99),
                "mapped_account_rows": int(len(matched)),
                "mapped_company_count": int(matched["company_count"].sum()) if not matched.empty else 0,
            }
        )

    return pd.DataFrame(rows).sort_values(["priority", "standard_account_id"])


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


def build_mapping_lookup(mapping_frame: pd.DataFrame) -> dict[tuple[str, str, str, str], tuple[str, str, str, int, str]]:
    lookup = mapping_frame[mapping_frame["standard_account_id"].notna()].copy()
    lookup = lookup[
        [
            "statement_type",
            "account_id_raw",
            "account_detail_raw",
            "account_nm_clean",
            "standard_account_id",
            "standard_account_nm",
            "account_bucket",
            "confidence",
            "mapping_rule",
        ]
    ].drop_duplicates()
    return {
        (row.statement_type, row.account_id_raw, row.account_detail_raw, row.account_nm_clean): (
            row.standard_account_id,
            row.standard_account_nm,
            row.account_bucket,
            int(row.confidence),
            row.mapping_rule,
        )
        for row in lookup.itertuples(index=False)
    }


def build_standard_financials(
    mapping_lookup: dict[tuple[str, str, str, str], tuple[str, str, str, int, str]],
) -> pd.DataFrame:
    if not RAW_DB.exists():
        raise FileNotFoundError(f"원본 DB가 없습니다: {RAW_DB}")

    candidate_account_ids = sorted(
        {
            account_id
            for (_, account_id) in ACCOUNT_ID_EXACT_MAP
            if account_id and account_id != UNMAPPED_ACCOUNT_ID
        }
    )
    candidate_clean_names = sorted(
        {
            clean_name
            for mappings in NAME_RULE_MAP.values()
            for clean_name in mappings
        }
    )
    account_id_sql = ", ".join(f"'{value}'" for value in candidate_account_ids)
    clean_name_sql = ", ".join(f"'{value}'" for value in candidate_clean_names)

    query = f"""
        SELECT
            corp_code AS company_id,
            corp_name AS company_name,
            stock_code,
            bsns_year AS year,
            sj_nm AS statement_type,
            account_id AS account_id_raw,
            account_nm AS account_nm_raw,
            account_detail AS account_detail_raw,
            thstrm_amount
        FROM financial_statements
        WHERE sj_nm IN ('재무상태표', '손익계산서', '포괄손익계산서', '현금흐름표')
          AND (
            account_id IN ({account_id_sql})
            OR REPLACE(TRIM(COALESCE(account_nm, '')), ' ', '') IN ({clean_name_sql})
          )
    """

    grouped_chunks: list[pd.DataFrame] = []
    with sqlite3.connect(RAW_DB) as connection:
        for chunk in pd.read_sql_query(query, connection, chunksize=100000):
            chunk["statement_type"] = chunk["statement_type"].fillna("").astype(str)
            chunk["account_id_raw"] = chunk["account_id_raw"].fillna("").astype(str)
            chunk["account_nm_raw"] = chunk["account_nm_raw"].fillna("").astype(str)
            chunk["account_detail_raw"] = chunk["account_detail_raw"].fillna("").astype(str)
            chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce")
            chunk["account_nm_clean"] = chunk["account_nm_raw"].map(clean_account_name)
            chunk["amount"] = chunk["thstrm_amount"].map(parse_amount)
            chunk["fs_type"] = UNKNOWN_FS_TYPE

            mapping_meta = [
                mapping_lookup.get(key)
                for key in zip(
                    chunk["statement_type"],
                    chunk["account_id_raw"],
                    chunk["account_detail_raw"],
                    chunk["account_nm_clean"],
                )
            ]

            chunk["standard_account_id"] = [meta[0] if meta else None for meta in mapping_meta]
            chunk["standard_account_nm"] = [meta[1] if meta else None for meta in mapping_meta]
            chunk["account_bucket"] = [meta[2] if meta else None for meta in mapping_meta]
            chunk["confidence"] = [meta[3] if meta else None for meta in mapping_meta]
            chunk["mapping_rule"] = [meta[4] if meta else None for meta in mapping_meta]

            mapped = chunk[chunk["standard_account_id"].notna() & chunk["amount"].notna()].copy()
            if mapped.empty:
                continue

            grouped = (
                mapped.groupby(
                    [
                        "company_id",
                        "company_name",
                        "stock_code",
                        "year",
                        "fs_type",
                        "statement_type",
                        "standard_account_id",
                        "standard_account_nm",
                        "account_bucket",
                    ],
                    dropna=False,
                )
                .agg(
                    amount=("amount", "sum"),
                    source_row_count=("amount", "size"),
                    source_account_names=("account_nm_raw", lambda values: " | ".join(sorted(set(values))[:5])),
                    source_account_ids=("account_id_raw", lambda values: " | ".join(sorted({value for value in values if value})[:5])),
                    max_confidence=("confidence", "max"),
                    mapping_rules=("mapping_rule", lambda values: " | ".join(sorted(set(values)))),
                )
                .reset_index()
            )
            grouped_chunks.append(grouped)

    if not grouped_chunks:
        return pd.DataFrame(
            columns=[
                "company_id",
                "company_name",
                "stock_code",
                "year",
                "fs_type",
                "statement_type",
                "standard_account_id",
                "standard_account_nm",
                "account_bucket",
                "amount",
                "source_row_count",
                "source_account_names",
                "source_account_ids",
                "max_confidence",
                "mapping_rules",
            ]
        )

    combined = pd.concat(grouped_chunks, ignore_index=True)
    final_grouped = (
        combined.groupby(
            [
                "company_id",
                "company_name",
                "stock_code",
                "year",
                "fs_type",
                "statement_type",
                "standard_account_id",
                "standard_account_nm",
                "account_bucket",
            ],
            dropna=False,
        )
        .agg(
            amount=("amount", "sum"),
            source_row_count=("source_row_count", "sum"),
            source_account_names=("source_account_names", lambda values: " | ".join(sorted(set(values))[:5])),
            source_account_ids=("source_account_ids", lambda values: " | ".join(sorted(set(values))[:5])),
            max_confidence=("max_confidence", "max"),
            mapping_rules=("mapping_rules", lambda values: " | ".join(sorted(set(values)))),
        )
        .reset_index()
        .sort_values(["company_id", "year", "statement_type", "standard_account_id"])
    )
    final_grouped["year"] = final_grouped["year"].astype("Int64")
    return final_grouped


def save_to_sqlite(
    mapping_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    dictionary_frame: pd.DataFrame,
    standard_financials_frame: pd.DataFrame,
) -> None:
    with sqlite3.connect(STANDARDS_DB) as connection:
        mapping_frame.to_sql("account_standard_mapping", connection, if_exists="replace", index=False)
        validation_frame.to_sql("account_core_validation", connection, if_exists="replace", index=False)
        dictionary_frame.to_sql("standard_account_dictionary", connection, if_exists="replace", index=False)
        standard_financials_frame.to_sql("standard_financials", connection, if_exists="replace", index=False)


def print_console_summary(
    mapping_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    dictionary_frame: pd.DataFrame,
    standard_financials_frame: pd.DataFrame,
) -> None:
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
    print(f"표준 계정 사전 수: {len(dictionary_frame):,}")
    print(f"표준 재무 팩트 행 수: {len(standard_financials_frame):,}")


def main() -> None:
    frame = load_accounts()
    normalized = preserve_raw_columns(frame)
    apply_review_holds(normalized)
    apply_account_id_mappings(normalized)
    apply_name_rule_mappings(normalized, include_any_account_id=False)
    apply_name_rule_mappings(normalized, include_any_account_id=True)
    apply_keyword_rule_mappings(normalized)
    finalize_review_flags(normalized)

    validation_frame = validate_core_accounts(normalized)
    output_frame = build_output_columns(normalized)
    dictionary_frame = build_standard_account_dictionary(output_frame)
    mapping_lookup = build_mapping_lookup(output_frame)
    standard_financials_frame = build_standard_financials(mapping_lookup)

    output_frame.to_csv(MAPPING_CSV, index=False, encoding="utf-8-sig")
    standard_financials_frame.to_csv(STANDARD_FINANCIALS_CSV, index=False, encoding="utf-8-sig")
    save_to_sqlite(output_frame, validation_frame, dictionary_frame, standard_financials_frame)
    print_console_summary(output_frame, validation_frame, dictionary_frame, standard_financials_frame)
    print(f"저장 완료: {MAPPING_CSV}")
    print(f"저장 완료: {STANDARD_FINANCIALS_CSV}")
    print(f"SQLite 반영 완료: {STANDARDS_DB}")


if __name__ == "__main__":
    main()
