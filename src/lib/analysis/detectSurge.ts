import type { RiskSignal } from "../../types/analysis";
import type { NormalizedFinancialData, StandardAccountKey } from "../../types/financial";

const monitoredAccounts: StandardAccountKey[] = [
  "accountsReceivable",
  "inventory",
  "intangibleAssets",
  "revenue",
  "operatingCashFlow"
];

export function detectAccountSurges(data: NormalizedFinancialData[]): RiskSignal[] {
  const sorted = data.slice().sort((a, b) => a.year - b.year);
  const results: RiskSignal[] = [];

  for (let index = 1; index < sorted.length; index += 1) {
    const previous = sorted[index - 1];
    const current = sorted[index];

    for (const accountKey of monitoredAccounts) {
      const previousValue = previous[accountKey];
      const currentValue = current[accountKey];

      if (
        previousValue === undefined ||
        currentValue === undefined ||
        previousValue === 0
      ) {
        continue;
      }

      const changeRate = (currentValue - previousValue) / Math.abs(previousValue);
      if (Math.abs(changeRate) < 0.3) {
        continue;
      }

      results.push({
        id: `${accountKey}-${current.year}`,
        year: current.year,
        accountKey,
        title: `${current.year}년 계정 변동`,
        description: `${accountKey} 계정이 전년 대비 ${(changeRate * 100).toFixed(1)}% 변동했습니다. 추가 검토가 필요할 수 있습니다.`,
        severity: Math.abs(changeRate) >= 0.5 ? "high" : "medium"
      });
    }
  }

  return results;
}
