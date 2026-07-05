import type { DebtRatioResult, NormalizedFinancialData } from "@/types/financial";

export function calculateDebtRatio(data: NormalizedFinancialData[]): DebtRatioResult[] {
  return data
    .slice()
    .sort((a, b) => a.year - b.year)
    .map((item) => {
      if (item.totalLiabilities === undefined) {
        return {
          year: item.year,
          totalLiabilities: null,
          totalEquity: item.totalEquity ?? null,
          debtRatio: null,
          debtRatioPercent: null,
          status: "missing_liabilities" as const
        };
      }

      if (item.totalEquity === undefined) {
        return {
          year: item.year,
          totalLiabilities: item.totalLiabilities,
          totalEquity: null,
          debtRatio: null,
          debtRatioPercent: null,
          status: "missing_equity" as const
        };
      }

      if (item.totalEquity === 0) {
        return {
          year: item.year,
          totalLiabilities: item.totalLiabilities,
          totalEquity: 0,
          debtRatio: null,
          debtRatioPercent: null,
          status: "zero_equity" as const
        };
      }

      const debtRatio = item.totalLiabilities / item.totalEquity;

      return {
        year: item.year,
        totalLiabilities: item.totalLiabilities,
        totalEquity: item.totalEquity,
        debtRatio,
        debtRatioPercent: debtRatio * 100,
        status: "ok" as const
      };
    });
}
