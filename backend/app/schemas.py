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


class FinancialStatementRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    corp_name: str = Field(alias="corpName")
    corp_code: str = Field(alias="corpCode")
    business_year: str = Field(alias="businessYear")
    statement_type: str = Field(alias="statementType")
    liabilities: float
    equity: float
    debt_ratio: float = Field(alias="debtRatio")
    unit: str
    liabilities_account_name: str = Field(alias="liabilitiesAccountName")
    equity_account_name: str = Field(alias="equityAccountName")
    updated_at: str = Field(alias="updatedAt")


class SamsungFinancialStatementsResponse(BaseModel):
    corp_name: str = Field(alias="corpName")
    corp_code: str = Field(alias="corpCode")
    count: int
    items: list[FinancialStatementRecord]


class SamsungFinancialStatementsSyncResponse(BaseModel):
    corp_name: str = Field(alias="corpName")
    corp_code: str = Field(alias="corpCode")
    inserted: int
    updated: int
    total: int
    years: list[str]
