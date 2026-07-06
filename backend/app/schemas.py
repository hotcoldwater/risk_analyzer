from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    error: bool = True
    message: str
    detail: Optional[str] = None


class DebtRatioResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    corp_name: str = Field(alias="corpName")
    corp_code: str = Field(alias="corpCode")
    year: str
    liabilities: float
    equity: float
    debt_ratio: float = Field(alias="debtRatio")
    unit: str = "KRW"
    source: str = "DART"
    cached: bool = False
    warnings: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: str
    liabilities: float
    equity: float
    liabilities_account_name: str = Field(alias="liabilitiesAccountName")
    equity_account_name: str = Field(alias="equityAccountName")
    statement_type: str = Field(alias="statementType")
    unit: str = "KRW"
