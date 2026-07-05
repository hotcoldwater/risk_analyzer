export type ReportCode = "11011" | "11012" | "11013" | "11014";
export type FsDiv = "CFS" | "OFS";

export type StandardAccountKey =
  | "revenue"
  | "operatingProfit"
  | "netIncome"
  | "operatingCashFlow"
  | "accountsReceivable"
  | "inventory"
  | "intangibleAssets"
  | "totalAssets"
  | "totalLiabilities"
  | "totalEquity";

export type NormalizedFinancialData = {
  year: number;
  fsDiv: FsDiv;
  reportCode: ReportCode;
  revenue?: number;
  operatingProfit?: number;
  netIncome?: number;
  operatingCashFlow?: number;
  accountsReceivable?: number;
  inventory?: number;
  intangibleAssets?: number;
  totalAssets?: number;
  totalLiabilities?: number;
  totalEquity?: number;
  rawItems?: unknown[];
};

export type DebtRatioResult = {
  year: number;
  totalLiabilities: number | null;
  totalEquity: number | null;
  debtRatio: number | null;
  debtRatioPercent: number | null;
  status: "ok" | "missing_liabilities" | "missing_equity" | "zero_equity";
};
