from __future__ import annotations

import re
from typing import Any


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if text in {"", "-", "nan", "None"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace(",", "").replace(" ", "").replace("(", "").replace(")", "")
    if cleaned in {"", "-"}:
        return None

    number = float(cleaned)
    return -number if negative else number


def is_corp_code(query: str) -> bool:
    return bool(re.fullmatch(r"\d{8}", query.strip()))


def is_stock_code(query: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", query.strip()))
