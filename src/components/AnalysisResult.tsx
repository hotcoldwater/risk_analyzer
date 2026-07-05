import { FinancialTable } from "@/components/FinancialTable";
import { RiskSummaryCard } from "@/components/RiskSummaryCard";
import { formatPercent } from "@/lib/utils/format";
import type { RiskSignal } from "@/types/analysis";
import type { CompanyProfile } from "@/types/dart";
import type { DebtRatioResult, FsDiv, ReportCode } from "@/types/financial";

type YearlyStatus = {
  year: number;
  fetched: boolean;
  fsDivUsed: FsDiv;
  fallbackApplied: boolean;
  error: string | null;
};

type Props = {
  company: CompanyProfile;
  financials: DebtRatioResult[];
  riskSignals: RiskSignal[];
  summary: string;
  period: {
    startYear: number;
    endYear: number;
    reportCode: ReportCode;
    fsDiv: FsDiv;
  };
  yearlyStatus: YearlyStatus[];
};

function buildPolyline(financials: DebtRatioResult[]) {
  const valid = financials.filter((item) => item.debtRatioPercent !== null);
  if (valid.length === 0) {
    return "";
  }

  const max = Math.max(...valid.map((item) => item.debtRatioPercent ?? 0), 1);
  return valid
    .map((item, index) => {
      const x = valid.length === 1 ? 200 : (index / (valid.length - 1)) * 360 + 20;
      const y = 180 - ((item.debtRatioPercent ?? 0) / max) * 140;
      return `${x},${y}`;
    })
    .join(" ");
}

export function AnalysisResult({
  company,
  financials,
  riskSignals,
  summary,
  period,
  yearlyStatus
}: Props) {
  const chartPoints = buildPolyline(financials);

  return (
    <section className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-line bg-white p-5 shadow-panel">
          <h3 className="text-lg font-semibold">기업 기본정보</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-xs text-slate-500">기업명</p>
              <p className="font-semibold">{company.corpName}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">종목코드</p>
              <p className="font-semibold">{company.stockCode || "N/A"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">DART 고유번호</p>
              <p className="font-semibold">{company.corpCode}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">업종코드</p>
              <p className="font-semibold">{company.industryCode || "N/A"}</p>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-line bg-white p-5 shadow-panel">
          <h3 className="text-lg font-semibold">분석 조건</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-xs text-slate-500">분석기간</p>
              <p className="font-semibold">
                {period.startYear} - {period.endYear}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">보고서 코드</p>
              <p className="font-semibold">{period.reportCode}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">요청 재무제표</p>
              <p className="font-semibold">{period.fsDiv}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">요약</p>
              <p className="font-semibold text-accent">{summary}</p>
            </div>
          </div>
        </div>
      </div>

      <FinancialTable financials={financials} />

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-line bg-white p-5 shadow-panel">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">부채비율 추이</h3>
            <p className="text-sm text-slate-500">단위: %</p>
          </div>

          {chartPoints ? (
            <svg viewBox="0 0 400 220" className="mt-4 w-full">
              <line x1="20" y1="180" x2="380" y2="180" stroke="#bcd0e0" strokeWidth="1" />
              <line x1="20" y1="20" x2="20" y2="180" stroke="#bcd0e0" strokeWidth="1" />
              <polyline
                fill="none"
                stroke="#0f7a95"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={chartPoints}
              />
              {financials
                .filter((item) => item.debtRatioPercent !== null)
                .map((item, index, array) => {
                  const max = Math.max(
                    ...array.map((entry) => entry.debtRatioPercent ?? 0),
                    1
                  );
                  const x = array.length === 1 ? 200 : (index / (array.length - 1)) * 360 + 20;
                  const y = 180 - ((item.debtRatioPercent ?? 0) / max) * 140;
                  return (
                    <g key={`point-${item.year}`}>
                      <circle cx={x} cy={y} r="5" fill="#0f7a95" />
                      <text x={x} y={205} textAnchor="middle" fontSize="12" fill="#475467">
                        {item.year}
                      </text>
                      <text x={x} y={y - 12} textAnchor="middle" fontSize="11" fill="#102033">
                        {formatPercent(item.debtRatioPercent)}
                      </text>
                    </g>
                  );
                })}
            </svg>
          ) : (
            <p className="mt-4 text-sm text-slate-600">그래프를 그릴 데이터가 부족합니다.</p>
          )}
        </div>

        <RiskSummaryCard signals={riskSignals} />
      </div>

      <div className="rounded-3xl border border-line bg-white p-5 shadow-panel">
        <h3 className="text-lg font-semibold">연도별 조회 상태</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {yearlyStatus.map((status) => (
            <div key={status.year} className="rounded-2xl border border-line bg-mist/50 p-4">
              <p className="font-semibold">{status.year}년</p>
              <p className="mt-1 text-sm text-slate-700">
                조회 결과: {status.fetched ? "성공" : "실패"}
              </p>
              <p className="mt-1 text-sm text-slate-700">사용 재무제표: {status.fsDivUsed}</p>
              <p className="mt-1 text-sm text-slate-700">
                연결 fallback: {status.fallbackApplied ? "적용" : "없음"}
              </p>
              {status.error ? <p className="mt-2 text-xs text-danger">{status.error}</p> : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
