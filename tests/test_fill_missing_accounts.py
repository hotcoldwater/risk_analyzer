"""Unit tests for scripts/dart/fill_missing_accounts.py's conflict-resolution
logic: when several raw DART account_nm rows match the same (corp_code, year,
fs_div) key, resolve_conflict() picks one using two rules --
  1. same label repeated -> lowest statement `ord` (its position in the filing) wins
  2. different label variants -> the order given in --account-variants wins
and refuses to guess when neither rule narrows it to a single row.
"""

import sqlite3

import pytest

from fill_missing_accounts import clean_field, normalize_corp_code, resolve_conflict


def _rows(*records: tuple[str, str, str]) -> list[sqlite3.Row]:
    """Build real sqlite3.Row objects (account_nm, ord, thstrm_amount) so the
    test exercises resolve_conflict() against the same row type production code uses."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE t (account_nm TEXT, ord TEXT, thstrm_amount TEXT)")
    connection.executemany("INSERT INTO t VALUES (?, ?, ?)", records)
    rows = connection.execute("SELECT * FROM t").fetchall()
    connection.close()
    return rows


def test_same_label_duplicated_picks_lowest_ord():
    """Same account_nm split across two lines (e.g. current/non-current breakdown) ->
    the row positioned first in the filing (lowest ord) is chosen."""
    matches = _rows(("영업이익", "5", "1000"), ("영업이익", "2", "2000"))
    chosen = resolve_conflict(("corp", "2024", "OFS"), matches, ["영업이익"])
    assert chosen["ord"] == "2"
    assert chosen["thstrm_amount"] == "2000"


def test_different_variants_pick_first_listed_priority():
    """Different account_nm variants for the same concept -> the variant listed
    first in --account-variants wins, regardless of ord."""
    matches = _rows(("IV.영업이익", "1", "500"), ("영업이익(손실)", "9", "700"))
    chosen = resolve_conflict(
        ("corp", "2024", "OFS"),
        matches,
        ["영업이익", "영업이익(손실)", "IV.영업이익"],
    )
    assert chosen["account_nm"] == "영업이익(손실)"


def test_variant_priority_skips_rows_with_no_value_first():
    """When the highest-priority variant has no reported amount, fall back to the
    next variant in priority order that actually has a value."""
    matches = _rows(("IV.영업이익", "3", ""), ("영업이익(손실)", "7", "900"))
    chosen = resolve_conflict(
        ("corp", "2024", "OFS"),
        matches,
        ["IV.영업이익", "영업이익(손실)"],
    )
    assert chosen["account_nm"] == "영업이익(손실)"
    assert chosen["thstrm_amount"] == "900"


def test_unresolvable_ambiguity_raises_instead_of_guessing():
    """Different labels, none of them present in --account-variants order (or
    ord doesn't apply because the labels differ) -> refuse to guess."""
    matches = _rows(("영업이익(손실)", "1", "100"), ("영업손익", "2", "200"))
    with pytest.raises(SystemExit):
        resolve_conflict(("corp", "2024", "OFS"), matches, ["당기순이익"])


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ('01199550"', "01199550"),
        (" 00123456 ", "00123456"),
    ],
)
def test_clean_field_strips_csv_export_artifacts(raw, cleaned):
    assert clean_field(raw) == cleaned


def test_normalize_corp_code_zero_pads_digit_only_codes():
    assert normalize_corp_code("1524093") == "01524093"
    assert normalize_corp_code("01524093") == "01524093"
