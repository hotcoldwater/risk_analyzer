"""Unit tests for scripts/pipeline/normalize_accounts.py's account-name
standardization/matching logic (clean_account_name + the rule-based mapping
passes run in normalize_accounts.main())."""

import pandas as pd
import pytest

from normalize_accounts import (
    apply_account_id_mappings,
    apply_keyword_rule_mappings,
    apply_name_rule_mappings,
    apply_review_holds,
    clean_account_name,
    finalize_review_flags,
    preserve_raw_columns,
)

UNMAPPED_ACCOUNT_ID = "-표준계정코드 미사용-"


def _row(sj_nm: str, account_nm: str, account_id: str = UNMAPPED_ACCOUNT_ID, account_detail: str = ""):
    return {
        "sj_nm": sj_nm,
        "account_nm": account_nm,
        "account_id": account_id,
        "account_detail": account_detail,
        "occurrences": 1,
        "company_count": 1,
    }


def _run_pipeline(rows: list[dict]) -> pd.DataFrame:
    """Reproduce the mapping pass order used by normalize_accounts.main()."""
    normalized = preserve_raw_columns(pd.DataFrame(rows))
    apply_review_holds(normalized)
    apply_account_id_mappings(normalized)
    apply_name_rule_mappings(normalized, include_any_account_id=False)
    apply_name_rule_mappings(normalized, include_any_account_id=True)
    apply_keyword_rule_mappings(normalized)
    finalize_review_flags(normalized)
    return normalized


@pytest.mark.parametrize(
    "account_nm, expected_standard_id",
    [
        ("매출액", "IS_REVENUE"),
        ("영업이익", "IS_OPERATING_INCOME"),
        ("영업이익(손실)", "IS_OPERATING_INCOME"),
        ("당기순손실", "IS_NET_INCOME"),
        ("당기순이익(손실)", "IS_NET_INCOME"),
    ],
)
def test_known_label_variants_map_to_the_same_standard_account(account_nm, expected_standard_id):
    """Different raw labels for the same concept must converge on one standard_account_id."""
    result = _run_pipeline([_row("손익계산서", account_nm)])
    assert result.loc[0, "standard_account_id"] == expected_standard_id


def test_whitespace_and_fullwidth_bracket_variants_are_normalized_before_matching():
    """clean_account_name folds spacing/full-width bracket noise so the name rule still hits."""
    result = _run_pipeline([_row("손익계산서", " 영업이익 （손실） ")])
    assert result.loc[0, "account_nm_clean"] == "영업이익(손실)"
    assert result.loc[0, "standard_account_id"] == "IS_OPERATING_INCOME"


def test_account_id_exact_match_takes_priority_over_name_rule():
    """A known XBRL account_id must win even when the label text itself doesn't match a name rule."""
    result = _run_pipeline([_row("손익계산서", "매출(수익)", account_id="ifrs-full_Revenue")])
    row = result.iloc[0]
    assert row["standard_account_id"] == "IS_REVENUE"
    assert row["mapping_rule"] == "account_id_exact"
    assert row["confidence"] == 100


def test_partial_score_variant_has_lower_confidence_than_exact_label():
    """'단기차입금'/'장기차입금' resolve to the same standard account as '차입금' but at
    lower confidence, since they're a qualified variant rather than the canonical label."""
    exact = _run_pipeline([_row("재무상태표", "차입금")]).iloc[0]
    variant = _run_pipeline([_row("재무상태표", "단기차입금")]).iloc[0]
    assert exact["standard_account_id"] == "BS_BORROWINGS"
    assert variant["standard_account_id"] == "BS_BORROWINGS"
    assert variant["confidence"] < exact["confidence"]


def test_numbered_prefix_variant_is_not_auto_normalized_and_needs_review():
    """'IV.영업이익' (a statement-position prefix) isn't stripped by clean_account_name, so
    normalize_accounts.py alone can't fold it into IS_OPERATING_INCOME -- this is the exact
    gap fill_missing_accounts.py's --account-variants list + ord tie-break exists to close."""
    result = _run_pipeline([_row("손익계산서", "IV.영업이익")])
    row = result.iloc[0]
    assert pd.isna(row["standard_account_id"])
    assert row["mapping_rule"] == "needs_review"


def test_review_hold_names_are_excluded_even_if_keyword_matches():
    """Ambiguous labels like '기타' must stay unmapped for manual review, not fall through to a keyword rule."""
    result = _run_pipeline([_row("재무상태표", "기타")])
    row = result.iloc[0]
    assert pd.isna(row["standard_account_id"])
    assert row["memo"] == "자동 매핑 제외: 의미 불명확"


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ("영업이익", "영업이익"),
        ("영업이익(손실)", "영업이익(손실)"),
        ("IV. 영업이익", "IV.영업이익"),
        (" 영업이익 ", "영업이익"),
        ("영업이익\n(손실)", "영업이익(손실)"),
    ],
)
def test_clean_account_name_normalizes_formatting_noise(raw, cleaned):
    assert clean_account_name(raw) == cleaned
