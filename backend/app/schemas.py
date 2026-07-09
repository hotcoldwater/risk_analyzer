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


class CompanySuggestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    company_name: str = Field(alias="companyName")
    stock_code: str | None = Field(default=None, alias="stockCode")
    market: str | None = None
    market_rank: int | None = Field(default=None, alias="marketRank")
    market_cap_krw: int | None = Field(default=None, alias="marketCapKrw")


class FinancialSeriesPoint(BaseModel):
    year: str
    revenue: float | None = None
    gross_profit: float | None = Field(default=None, alias="grossProfit")
    operating_income: float | None = Field(default=None, alias="operatingIncome")
    net_income: float | None = Field(default=None, alias="netIncome")


class CompanyOverviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    company_name: str = Field(alias="companyName")
    stock_code: str | None = Field(default=None, alias="stockCode")
    market: str | None = None
    market_rank: int | None = Field(default=None, alias="marketRank")
    market_cap_krw: int | None = Field(default=None, alias="marketCapKrw")
    current_price_krw: int | None = Field(default=None, alias="currentPriceKrw")
    series: list[FinancialSeriesPoint]


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


class MultiAnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    analysis_count: int = Field(alias="analysisCount")
    items: list[AnalysisResponse]


class CompanyProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: dict
    groups: list[dict]
    analyses: list[dict]


class LiquiditySeriesPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int
    company_value: float | None = Field(default=None, alias="companyValue")
    company_display: str = Field(alias="companyDisplay")
    average_value: float | None = Field(default=None, alias="averageValue")
    average_display: str = Field(alias="averageDisplay")
    sample_size: int = Field(alias="sampleSize")
    source_basis: str | None = Field(default=None, alias="sourceBasis")
    source_label: str = Field(alias="sourceLabel")
    reason: str | None = None


class MetricDetailRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    current_value: float | str | None = Field(default=None, alias="currentValue")
    current_display: str = Field(alias="currentDisplay")
    previous_value: float | str | None = Field(default=None, alias="previousValue")
    previous_display: str = Field(alias="previousDisplay")
    note: str | None = None


class LiquidityMetricResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: dict
    metric_code: str = Field(alias="metricCode")
    metric_name: str = Field(alias="metricName")
    metric_description: str = Field(alias="metricDescription")
    year: int
    group_scope: str = Field(alias="groupScope")
    source_basis: str | None = Field(default=None, alias="sourceBasis")
    source_label: str = Field(alias="sourceLabel")
    current_value: float | None = Field(default=None, alias="currentValue")
    current_display: str = Field(alias="currentDisplay")
    current_reason: str | None = Field(default=None, alias="currentReason")
    average_value: float | None = Field(default=None, alias="averageValue")
    average_display: str = Field(alias="averageDisplay")
    average_sample_size: int = Field(alias="averageSampleSize")
    series: list[LiquiditySeriesPoint]
    details: list[MetricDetailRow]
    formula: str


class AnomalyIndicator(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    value: float | None = None
    display: str
    description: str


class AnomalySignal(BaseModel):
    code: str
    title: str
    triggered: bool
    severity: str
    summary: str


class AnomalyAnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: dict
    year: int
    group_scope: str = Field(alias="groupScope")
    source_basis: str | None = Field(default=None, alias="sourceBasis")
    source_label: str = Field(alias="sourceLabel")
    overall_risk_level: str = Field(alias="overallRiskLevel")
    overall_summary: str = Field(alias="overallSummary")
    note: str | None = None
    indicators: list[AnomalyIndicator]
    signals: list[AnomalySignal]
    contract_asset_risk: dict = Field(alias="contractAssetRisk")
