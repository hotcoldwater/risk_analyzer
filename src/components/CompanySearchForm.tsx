"use client";

import { useState } from "react";
import type { CorpSummary } from "@/types/dart";
import type { FsDiv, ReportCode } from "@/types/financial";

type SearchResponse = {
  success: boolean;
  data?: CorpSummary[];
  error?: string;
};

type AnalyzeFormValues = {
  corpCode: string;
  corpName: string;
  startYear: number;
  endYear: number;
  reportCode: ReportCode;
  fsDiv: FsDiv;
};

type Props = {
  onAnalyze: (values: AnalyzeFormValues) => Promise<void>;
  loading: boolean;
};

const reportCodeOptions: Array<{ value: ReportCode; label: string }> = [
  { value: "11011", label: "사업보고서" },
  { value: "11012", label: "반기보고서" },
  { value: "11013", label: "1분기보고서" },
  { value: "11014", label: "3분기보고서" }
];

const fsDivOptions: Array<{ value: FsDiv; label: string }> = [
  { value: "CFS", label: "연결재무제표" },
  { value: "OFS", label: "별도재무제표" }
];

const currentYear = new Date().getFullYear();

export function CompanySearchForm({ onAnalyze, loading }: Props) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CorpSummary[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<CorpSummary | null>(null);
  const [startYear, setStartYear] = useState(currentYear - 4);
  const [endYear, setEndYear] = useState(currentYear);
  const [reportCode, setReportCode] = useState<ReportCode>("11011");
  const [fsDiv, setFsDiv] = useState<FsDiv>("CFS");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const yearOptions = Array.from({ length: 10 }, (_, index) => currentYear - index);

  async function handleSearch() {
    setSearchLoading(true);
    setSearchError(null);
    setSelectedCompany(null);

    try {
      const response = await fetch(`/api/search-company?query=${encodeURIComponent(query)}`);
      const result = (await response.json()) as SearchResponse;

      if (!result.success) {
        throw new Error(result.error || "기업을 찾을 수 없습니다.");
      }

      setSearchResults(result.data ?? []);
      if ((result.data ?? []).length === 0) {
        setSearchError("기업을 찾을 수 없습니다.");
      }
    } catch (error) {
      setSearchResults([]);
      setSearchError(error instanceof Error ? error.message : "기업 검색 중 오류가 발생했습니다.");
    } finally {
      setSearchLoading(false);
    }
  }

  async function handleAnalyze() {
    if (!selectedCompany) {
      setSearchError("검색 결과에서 기업을 선택해 주세요.");
      return;
    }

    await onAnalyze({
      corpCode: selectedCompany.corpCode,
      corpName: selectedCompany.corpName,
      startYear,
      endYear,
      reportCode,
      fsDiv
    });
  }

  return (
    <section className="rounded-3xl border border-line bg-white p-6 shadow-panel">
      <div className="grid gap-5 lg:grid-cols-[2fr_1fr_1fr]">
        <div className="lg:col-span-3">
          <label className="mb-2 block text-sm font-semibold">기업명 검색</label>
          <div className="flex gap-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="예: 삼성전자"
              className="w-full rounded-2xl border border-line px-4 py-3 outline-none ring-0 transition focus:border-accent"
            />
            <button
              type="button"
              onClick={handleSearch}
              disabled={searchLoading || !query.trim()}
              className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
            >
              {searchLoading ? "검색 중" : "검색"}
            </button>
          </div>
        </div>

        <label className="block text-sm font-semibold">
          시작연도
          <select
            value={startYear}
            onChange={(event) => setStartYear(Number(event.target.value))}
            className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3"
          >
            {yearOptions.map((year) => (
              <option key={`start-${year}`} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold">
          종료연도
          <select
            value={endYear}
            onChange={(event) => setEndYear(Number(event.target.value))}
            className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3"
          >
            {yearOptions.map((year) => (
              <option key={`end-${year}`} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold">
          보고서 유형
          <select
            value={reportCode}
            onChange={(event) => setReportCode(event.target.value as ReportCode)}
            className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3"
          >
            {reportCodeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold lg:max-w-sm">
          재무제표 구분
          <select
            value={fsDiv}
            onChange={(event) => setFsDiv(event.target.value as FsDiv)}
            className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3"
          >
            {fsDivOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {searchError ? <p className="mt-4 text-sm text-danger">{searchError}</p> : null}

      {searchResults.length > 0 ? (
        <div className="mt-5 rounded-2xl border border-line bg-mist/70 p-3">
          <p className="mb-3 text-sm font-semibold">검색 결과</p>
          <div className="grid gap-2">
            {searchResults.map((company) => {
              const active = selectedCompany?.corpCode === company.corpCode;
              return (
                <button
                  key={company.corpCode}
                  type="button"
                  onClick={() => setSelectedCompany(company)}
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? "border-accent bg-accentSoft"
                      : "border-line bg-white hover:border-accent/50"
                  }`}
                >
                  <div className="font-semibold">{company.corpName}</div>
                  <div className="mt-1 text-xs text-slate-600">
                    종목코드 {company.stockCode || "N/A"} / DART {company.corpCode}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <button
        type="button"
        onClick={handleAnalyze}
        disabled={loading || !selectedCompany}
        className="mt-5 rounded-2xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50"
      >
        {loading ? "분석 중" : "분석 실행"}
      </button>
    </section>
  );
}
