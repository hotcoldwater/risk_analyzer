"use client";

import { useState } from "react";
import { AnalysisResult } from "@/components/AnalysisResult";
import { CompanySearchForm } from "@/components/CompanySearchForm";
import type { RiskSignal } from "@/types/analysis";
import type { CompanyProfile } from "@/types/dart";
import type { DebtRatioResult, FsDiv, ReportCode } from "@/types/financial";

type AnalysisResponse = {
  success: boolean;
  data?: {
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
    yearlyStatus: Array<{
      year: number;
      fetched: boolean;
      fsDivUsed: FsDiv;
      fallbackApplied: boolean;
      error: string | null;
    }>;
  };
  error?: string;
};

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse["data"]>();

  async function handleAnalyze(values: {
    corpCode: string;
    corpName: string;
    startYear: number;
    endYear: number;
    reportCode: ReportCode;
    fsDiv: FsDiv;
  }) {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(values)
      });

      const payload = (await response.json()) as AnalysisResponse;

      if (!payload.success || !payload.data) {
        throw new Error(payload.error || "분석 중 오류가 발생했습니다.");
      }

      setResult(payload.data);
    } catch (analyzeError) {
      setResult(undefined);
      setError(analyzeError instanceof Error ? analyzeError.message : "분석 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(212,240,246,0.95),_rgba(237,244,251,0.85)_35%,_rgba(237,244,251,1)_100%)] px-4 py-10">
      <div className="mx-auto max-w-6xl">
        <section className="mb-8 rounded-[2rem] bg-ink px-6 py-10 text-white shadow-panel">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-100">
            Audit-focused MVP
          </p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight sm:text-4xl">
            DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-slate-200 sm:text-base">
            기업 검색, 실제 DART 재무제표 조회, 부채비율 계산, 기본 위험 신호 분석까지 한 화면에서 확인합니다.
          </p>
        </section>

        <div className="grid gap-6">
          <CompanySearchForm onAnalyze={handleAnalyze} loading={loading} />

          {error ? (
            <section className="rounded-3xl border border-red-200 bg-red-50 p-5 text-danger shadow-panel">
              {error}
            </section>
          ) : null}

          {result ? (
            <AnalysisResult
              company={result.company}
              financials={result.financials}
              riskSignals={result.riskSignals}
              summary={result.summary}
              period={result.period}
              yearlyStatus={result.yearlyStatus}
            />
          ) : (
            <section className="rounded-3xl border border-line bg-white p-6 shadow-panel">
              <h2 className="text-lg font-semibold">안내</h2>
              <p className="mt-3 text-sm text-slate-700">
                기업 검색 후 분석 조건을 선택하면 연도별 부채총계, 자본총계, 부채비율과 기본 위험 신호를 확인할 수 있습니다.
              </p>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
