import type { RiskSignal } from "@/types/analysis";

type Props = {
  signals: RiskSignal[];
};

const severityLabel = {
  low: "낮음",
  medium: "중간",
  high: "높음"
} as const;

export function RiskSummaryCard({ signals }: Props) {
  return (
    <div className="rounded-3xl border border-line bg-white p-5 shadow-panel">
      <h3 className="text-lg font-semibold">기본 위험 신호</h3>
      {signals.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">
          현재 규칙 기준으로 뚜렷한 이상징후는 감지되지 않았습니다. 다만 추가 검토가 필요할 수 있습니다.
        </p>
      ) : (
        <div className="mt-4 grid gap-3">
          {signals.map((signal) => (
            <article key={signal.id} className="rounded-2xl border border-line bg-mist/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <h4 className="font-semibold">{signal.title}</h4>
                <span className="text-xs font-semibold text-warn">
                  위험도 {severityLabel[signal.severity]}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-700">{signal.description}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
