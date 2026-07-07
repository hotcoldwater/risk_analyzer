import { useEffect, useMemo, useState } from "react";

import {
  fetchAnalyses,
  fetchCompanyOverview,
  fetchCompanySearch,
  runAnalysis,
  runAnalyses,
} from "./api";

const primaryAnalysisCodes = [
  "DEBT_RATIO",
  "OPERATING_MARGIN",
  "NET_MARGIN",
  "GROSS_MARGIN",
  "INTEREST_COVERAGE",
  "OCF_TO_NET_INCOME",
];

function formatCompactKrw(value) {
  if (value == null) {
    return "N/A";
  }
  const absolute = Math.abs(value);
  if (absolute >= 1_0000_0000_0000) {
    return `${(value / 1_0000_0000_0000).toFixed(1)}조`;
  }
  if (absolute >= 1_0000_0000) {
    return `${(value / 1_0000_0000).toFixed(1)}억`;
  }
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value);
}

function TrendCard({ title, points, accessor }) {
  const values = points.map((point) => accessor(point)).filter((value) => value != null);
  const current = values.at(-1) ?? null;

  if (!values.length) {
    return (
      <article className="trend-card">
        <span>{title}</span>
        <strong>N/A</strong>
      </article>
    );
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;

  const polyline = points
    .map((point, index) => {
      const value = accessor(point);
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const y = value == null ? 50 : 100 - ((value - minValue) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <article className="trend-card">
      <span>{title}</span>
      <strong>{formatCompactKrw(current)}</strong>
      <svg className="trend-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polyline fill="none" points={polyline} stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="trend-years">
        {points.map((point) => (
          <em key={`${title}-${point.year}`}>{point.year}</em>
        ))}
      </div>
    </article>
  );
}

function SingleResultModal({ result, onClose }) {
  if (!result) {
    return null;
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <section className="result-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-head">
          <div>
            <p className="modal-kicker">{result.analysisName}</p>
            <h3>{result.companyName}</h3>
            <p className="modal-meta">{result.year}</p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            닫기
          </button>
        </header>

        <div className="metric-grid">
          {result.metrics.map((metric) => (
            <article key={metric.label} className="metric-panel">
              <span>{metric.label}</span>
              <strong className={metric.tone === "primary" ? "metric-primary" : ""}>{metric.value}</strong>
            </article>
          ))}
        </div>

        <div className="detail-grid">
          <article className="detail-panel">
            <h4>핵심</h4>
            <ul>
              {result.highlights.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
          <article className="detail-panel">
            <h4>경고</h4>
            {result.warnings.length ? (
              <ul>
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p className="empty-text">경고 없음</p>
            )}
          </article>
        </div>
      </section>
    </div>
  );
}

function ReportModal({ results, onClose }) {
  if (!results.length) {
    return null;
  }

  const first = results[0];

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <section className="report-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-head">
          <div>
            <p className="modal-kicker">리포트 센터</p>
            <h3>{first.companyName}</h3>
            <p className="modal-meta">{results.length}개 분석</p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            닫기
          </button>
        </header>

        <div className="report-stack">
          {results.map((result) => (
            <section key={result.analysisCode} className="report-block">
              <div className="report-block-head">
                <h4>{result.analysisName}</h4>
                <p>{result.summary}</p>
              </div>
              <div className="metric-grid compact">
                {result.metrics.map((metric) => (
                  <article key={`${result.analysisCode}-${metric.label}`} className="metric-panel">
                    <span>{metric.label}</span>
                    <strong className={metric.tone === "primary" ? "metric-primary" : ""}>{metric.value}</strong>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>
    </div>
  );
}

function App() {
  const [mode, setMode] = useState("company");
  const [query, setQuery] = useState("");
  const [analyses, setAnalyses] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [overview, setOverview] = useState(null);
  const [singleResult, setSingleResult] = useState(null);
  const [reportResults, setReportResults] = useState([]);
  const [selectedReportCodes, setSelectedReportCodes] = useState([]);
  const [error, setError] = useState("");
  const [isLoadingAnalyses, setIsLoadingAnalyses] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [isOverviewLoading, setIsOverviewLoading] = useState(false);
  const [isReportLoading, setIsReportLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadAnalyses() {
      try {
        const data = await fetchAnalyses();
        if (!isMounted) {
          return;
        }
        setAnalyses(data);
        setSelectedReportCodes(data.map((item) => item.analysisCode));
      } catch (caught) {
        if (!isMounted) {
          return;
        }
        setError(caught instanceof Error ? caught.message : "분석 목록을 불러오지 못했습니다.");
      } finally {
        if (isMounted) {
          setIsLoadingAnalyses(false);
        }
      }
    }

    loadAnalyses();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }

    let active = true;
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const items = await fetchCompanySearch(query);
        if (active) {
          setSuggestions(items);
        }
      } catch {
        if (active) {
          setSuggestions([]);
        }
      } finally {
        if (active) {
          setIsSearching(false);
        }
      }
    }, 150);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  const primaryAnalyses = useMemo(
    () => analyses.filter((item) => primaryAnalysisCodes.includes(item.analysisCode)),
    [analyses],
  );

  async function loadOverview(company) {
    setSelectedCompany(company);
    setQuery(company.companyName);
    setSuggestions([]);
    setIsOverviewLoading(true);
    setError("");

    try {
      const data = await fetchCompanyOverview(company.companyId);
      setOverview(data);
    } catch (caught) {
      setOverview(null);
      setError(caught instanceof Error ? caught.message : "개요 조회에 실패했습니다.");
    } finally {
      setIsOverviewLoading(false);
    }
  }

  async function handleSingleAnalysis(analysisCode) {
    if (!selectedCompany) {
      setError("기업을 먼저 선택해 주세요.");
      return;
    }
    setError("");
    try {
      const data = await runAnalysis(selectedCompany.companyId, analysisCode);
      setSingleResult(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "분석을 완료하지 못했습니다.");
    }
  }

  async function handleReportRun() {
    if (!selectedCompany) {
      setError("기업을 먼저 선택해 주세요.");
      return;
    }
    if (!selectedReportCodes.length) {
      setError("리포트에 포함할 분석을 선택해 주세요.");
      return;
    }

    setIsReportLoading(true);
    setError("");
    try {
      const data = await runAnalyses(selectedCompany.companyId, selectedReportCodes);
      setReportResults(data.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "리포트 생성에 실패했습니다.");
    } finally {
      setIsReportLoading(false);
    }
  }

  function toggleReportCode(code) {
    setSelectedReportCodes((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <button className={`nav-link ${mode === "company" ? "active" : ""}`} onClick={() => setMode("company")} type="button">
          기업 분석
        </button>
        <button className={`nav-link ${mode === "report" ? "active" : ""}`} onClick={() => setMode("report")} type="button">
          리포트 센터
        </button>
      </aside>

      <main className="app-main">
        <header className="topbar">
          <h1>재무제표 분석</h1>
          {selectedCompany ? (
            <div className="company-badge">
              <strong>{selectedCompany.companyName}</strong>
              <span>{selectedCompany.stockCode || selectedCompany.companyId}</span>
            </div>
          ) : null}
        </header>

        <section className="search-strip">
          <div className="search-field">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="기업명 또는 종목코드"
              type="text"
            />
            {suggestions.length ? (
              <div className="suggestion-box">
                {suggestions.map((item) => (
                  <button key={item.companyId} className="suggestion-item" onClick={() => loadOverview(item)} type="button">
                    <div>
                      <strong>{item.companyName}</strong>
                      <span>{item.stockCode || item.companyId}</span>
                    </div>
                    <em>{formatCompactKrw(item.marketCapKrw)}</em>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <button
            className="primary-button"
            disabled={!selectedCompany || isOverviewLoading}
            onClick={() => loadOverview(selectedCompany)}
            type="button"
          >
            {isSearching ? "검색 중" : isOverviewLoading ? "조회 중" : "조회"}
          </button>
        </section>

        {error ? <div className="status-bar error">{error}</div> : null}

        {mode === "company" ? (
          <section className="workspace">
            {overview ? (
              <>
                <div className="summary-strip">
                  <div>
                    <span>시가총액</span>
                    <strong>{formatCompactKrw(overview.marketCapKrw)}</strong>
                  </div>
                  <div>
                    <span>현재가</span>
                    <strong>{formatCompactKrw(overview.currentPriceKrw)}</strong>
                  </div>
                  <div>
                    <span>시장</span>
                    <strong>{overview.market || "N/A"}</strong>
                  </div>
                </div>

                <div className="trend-grid">
                  <TrendCard accessor={(point) => point.revenue} points={overview.series} title="매출" />
                  <TrendCard accessor={(point) => point.grossProfit} points={overview.series} title="매출총이익" />
                  <TrendCard accessor={(point) => point.operatingIncome} points={overview.series} title="영업이익" />
                  <TrendCard accessor={(point) => point.netIncome} points={overview.series} title="당기순이익" />
                </div>

                <div className="action-section">
                  <div className="section-title-row">
                    <h2>개별 분석</h2>
                  </div>
                  <div className="action-grid">
                    {primaryAnalyses.map((analysis) => (
                      <button
                        key={analysis.analysisCode}
                        className="action-card"
                        onClick={() => handleSingleAnalysis(analysis.analysisCode)}
                        type="button"
                      >
                        <strong>{analysis.analysisName}</strong>
                        <span>{analysis.notes}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-stage">기업을 선택하면 3개년 흐름이 표시됩니다.</div>
            )}
          </section>
        ) : (
          <section className="workspace report-layout">
            <div className="report-sidebar">
              <div className="section-title-row">
                <h2>리포트 센터</h2>
              </div>
              <div className="report-list">
                {analyses.map((analysis) => (
                  <label key={analysis.analysisCode} className="report-item">
                    <input
                      checked={selectedReportCodes.includes(analysis.analysisCode)}
                      onChange={() => toggleReportCode(analysis.analysisCode)}
                      type="checkbox"
                    />
                    <div>
                      <strong>{analysis.analysisName}</strong>
                      <span>{analysis.notes}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="report-main">
              <div className="report-meta">
                <div>
                  <span>대상 기업</span>
                  <strong>{selectedCompany ? selectedCompany.companyName : "미선택"}</strong>
                </div>
                <div>
                  <span>선택 분석</span>
                  <strong>{selectedReportCodes.length}</strong>
                </div>
              </div>
              <button className="primary-button wide" disabled={isLoadingAnalyses || isReportLoading} onClick={handleReportRun} type="button">
                {isReportLoading ? "리포트 생성 중" : "리포트 생성"}
              </button>
            </div>
          </section>
        )}
      </main>

      <SingleResultModal onClose={() => setSingleResult(null)} result={singleResult} />
      <ReportModal onClose={() => setReportResults([])} results={reportResults} />
    </div>
  );
}

export default App;
