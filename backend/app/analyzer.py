from __future__ import annotations


def calculate_debt_ratio(liabilities: float, equity: float) -> float:
    if equity <= 0:
        raise ValueError("자본이 0 이하이므로 부채비율을 계산할 수 없습니다.")

    return round((liabilities / equity) * 100, 1)
