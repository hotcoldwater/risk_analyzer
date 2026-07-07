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


class AnalysisDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    analysis_code: str = Field(alias="analysisCode")
    analysis_name: str = Field(alias="analysisName")
    analysis_group: str = Field(alias="analysisGroup")
    notes: str | None = None


class AnalysisMetric(BaseModel):
    label: str
    value: str
    unit: str | None = None
    tone: str = "default"


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    company_name: str = Field(alias="companyName")
    stock_code: str | None = Field(default=None, alias="stockCode")
    analysis_code: str = Field(alias="analysisCode")
    analysis_name: str = Field(alias="analysisName")
    analysis_group: str = Field(alias="analysisGroup")
    year: str
    summary: str
    source: str = "Supabase"
    available_years: list[str] = Field(alias="availableYears")
    metrics: list[AnalysisMetric]
    highlights: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
