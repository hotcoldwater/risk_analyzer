import type { RiskSignal } from "@/types/analysis";
import type { NormalizedFinancialData } from "@/types/financial";

export function analyzeCashFlowGap(data: NormalizedFinancialData[]): RiskSignal[] {
  return data.flatMap((item) => {
    const signals: RiskSignal[] = [];
    const { netIncome, operatingCashFlow } = item;

    if (netIncome === undefined || operatingCashFlow === undefined) {
      return signals;
    }

    if (netIncome > 0 && operatingCashFlow < 0) {
      signals.push({
        id: `cashflow-negative-${item.year}`,
        year: item.year,
        accountKey: "operatingCashFlow",
        title: `${item.year}년 순이익-현금흐름 괴리`,
        description:
          "순이익은 흑자이지만 영업활동현금흐름은 적자입니다. 이익의 질에 대한 추가 검토가 필요할 수 있습니다.",
        severity: "high"
      });
    }

    if (netIncome > 0 && operatingCashFlow / netIncome < 0.5) {
      signals.push({
        id: `cashflow-ratio-${item.year}`,
        year: item.year,
        accountKey: "operatingCashFlow",
        title: `${item.year}년 현금창출력 약화`,
        description:
          "영업활동현금흐름이 순이익 대비 낮게 나타났습니다. 수익 인식 또는 운전자본 변동 검토가 필요할 수 있습니다.",
        severity: "medium"
      });
    }

    return signals;
  });
}
