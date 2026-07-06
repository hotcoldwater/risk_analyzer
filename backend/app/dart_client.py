from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import dart_fss as dart

from app.config import get_settings
from app.normalizer import is_corp_code, is_stock_code


class CorporationNotFoundError(ValueError):
    pass


@dataclass
class CorporationMatch:
    corp: object
    warnings: list[str]


def initialize_dart() -> None:
    settings = get_settings()
    dart.set_api_key(api_key=settings.dart_api_key)


@lru_cache(maxsize=1)
def get_corp_list():
    initialize_dart()
    return dart.get_corp_list()


def find_corporation(query: str) -> CorporationMatch:
    normalized = query.strip()
    if not normalized:
        raise CorporationNotFoundError("기업명 또는 기업번호를 입력해 주세요.")

    corp_list = get_corp_list()
    warnings: list[str] = []

    if is_corp_code(normalized):
        corp = corp_list.find_by_corp_code(normalized)
        if corp is None:
            raise CorporationNotFoundError("해당 corp_code에 해당하는 기업을 찾을 수 없습니다.")
        return CorporationMatch(corp=corp, warnings=warnings)

    if is_stock_code(normalized):
        corp = corp_list.find_by_stock_code(normalized)
        if corp is None:
            raise CorporationNotFoundError("해당 종목코드에 해당하는 기업을 찾을 수 없습니다.")
        return CorporationMatch(corp=corp, warnings=warnings)

    exact_matches = corp_list.find_by_corp_name(normalized, exactly=True)
    if exact_matches:
        corp = exact_matches[0]
        if len(exact_matches) > 1:
            warnings.append("동일한 기업명이 여러 건 검색되어 첫 번째 정확 일치 기업을 사용했습니다.")
        return CorporationMatch(corp=corp, warnings=warnings)

    partial_matches = corp_list.find_by_corp_name(normalized, exactly=False)
    if not partial_matches:
        raise CorporationNotFoundError("기업을 찾을 수 없습니다.")

    if len(partial_matches) > 1:
        warnings.append("부분 일치 결과가 여러 건 검색되어 첫 번째 기업을 사용했습니다.")

    return CorporationMatch(corp=partial_matches[0], warnings=warnings)
