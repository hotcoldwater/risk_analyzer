import { formatKoreanCurrency, formatPercent } from "@/lib/utils/format";
import type { DebtRatioResult } from "@/types/financial";

type Props = {
  financials: DebtRatioResult[];
};

function getStatusLabel(status: DebtRatioResult["status"]) {
  switch (status) {
    case "missing_liabilities":
      return "부채총계 누락";
    case "missing_equity":
      return "자본총계 누락";
    case "zero_equity":
      return "자본 0";
    default:
      return "정상";
  }
}

export function FinancialTable({ financials }: Props) {
  return (
    <div className="overflow-hidden rounded-3xl border border-line bg-white shadow-panel">
      <div className="border-b border-line px-5 py-4">
        <h3 className="text-lg font-semibold">연도별 부채비율</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-mist/70 text-left">
            <tr>
              <th className="px-5 py-3">연도</th>
              <th className="px-5 py-3">부채총계</th>
              <th className="px-5 py-3">자본총계</th>
              <th className="px-5 py-3">부채비율</th>
              <th className="px-5 py-3">상태</th>
            </tr>
          </thead>
          <tbody>
            {financials.map((item) => (
              <tr key={item.year} className="border-t border-line">
                <td className="px-5 py-4 font-semibold">{item.year}</td>
                <td className="px-5 py-4">{formatKoreanCurrency(item.totalLiabilities)}</td>
                <td className="px-5 py-4">{formatKoreanCurrency(item.totalEquity)}</td>
                <td className="px-5 py-4">{formatPercent(item.debtRatioPercent)}</td>
                <td className="px-5 py-4 text-slate-600">{getStatusLabel(item.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
