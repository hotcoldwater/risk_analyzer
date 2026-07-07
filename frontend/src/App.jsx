import { useEffect, useState } from "react";

import { fetchAnalyses, runAnalysis } from "./api";

const recentQueries = ["삼성전자", "SK하이닉스", "00126380"];

function App() {
  const [query, setQuery] = useState("");
  const [selectedAnalysis, setSelectedAnalysis] = useState("");
  const [analyses, setAnalyses] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingAnalyses, setIsLoadingAnalyses] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadAnalyses() {
      try {
        const data = await fetchAnalyses();
        if (!isMounted) {
          return;
        }
        setAnalyses(data);
        setSelectedAnalysis(data[0]?.analysisCode || "");
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

  async function handleAnalyze(nextQuery) {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setError("기업명 또는 기업코드를 입력해 주세요.");
      setResult(null);
      return;
    }
    if (!selectedAnalysis) {
      setError("분석 항목을 선택해 주세요.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const data = await runAnalysis(trimmed, selectedAnalysis);
      setResult(data);
    } catch (caught) {
      setResult(null);
      if (caught instanceof Error) {
        setError(caught.message);
      } else {
        setError("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="landing-shell">
      <main className="landing-main">
        <section className="landing-card">
          <p className="eyebrow">AuditRisk-AI</p>
          <h1>DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스</h1>
          <p className="landing-copy">
            기업명 또는 기업코드를 입력하고 분석 항목을 선택하면, Supabase에 적재된 표준화
            재무데이터를 바탕으로 결과를 팝업 형태로 제공합니다.
          </p>

          <div className="search-panel">
            <label className="search-label" htmlFor="corp-query">
              기업명 또는 기업코드
            </label>
            <input
              id="corp-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="예: 삼성전자 또는 00126380"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleAnalyze(query);
                }
              }}
            />

            <label className="search-label" htmlFor="analysis-select">
              분석 항목
            </label>
            <select
              id="analysis-select"
              value={selectedAnalysis}
              onChange={(event) => setSelectedAnalysis(event.target.value)}
              disabled={isLoadingAnalyses}
            >
              <option value="">{isLoadingAnalyses ? "분석 목록 불러오는 중..." : "분석 항목을 선택하세요"}</option>
              {analyses.map((analysis) => (
                <option key={analysis.analysisCode} value={analysis.analysisCode}>
                  {analysis.analysisName}
                </option>
              ))}
            </select>

            <button disabled={isLoading || isLoadingAnalyses} onClick={() => handleAnalyze(query)} type="button">
              {isLoading ? "분석 중..." : "분석하기"}
            </button>

            <div className="recent-list">
              <span>최근 예시</span>
              {recentQueries.map((item) => (
                <button key={item} className="recent-chip" onClick={() => setQuery(item)} type="button">
                  {item}
                </button>
              ))}
            </div>
          </div>
        </section>

        {error ? (
          <div className="message-card error-card">
            <p className="message-title">분석을 완료하지 못했습니다.</p>
            <p>{error}</p>
          </div>
        ) : null}

        {!result && !isLoading && !error ? (
          <div className="message-card idle-card">
            <p className="message-title">분석 대기 중입니다.</p>
            <p>기업과 분석 항목을 선택한 뒤 분석 버튼을 눌러 주세요.</p>
          </div>
        ) : null}
      </main>

      {result ? (
        <div className="modal-backdrop" onClick={() => setResult(null)} role="presentation">
          <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal-head">
              <div>
                <p className="eyebrow">Analysis Result</p>
                <h2>{result.analysisName}</h2>
                <p className="corp-code">
                  {result.companyName} · {result.companyId} · {result.year}
                </p>
              </div>
              <button className="modal-close" onClick={() => setResult(null)} type="button">
                닫기
              </button>
            </div>

            <p className="modal-summary">{result.summary}</p>

            <div className="modal-grid">
              {result.metrics.map((metric) => (
                <article
                  key={metric.label}
                  className={`data-card ${metric.tone === "primary" ? "hero-metric" : ""}`}
                >
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                </article>
              ))}
            </div>

            <div className="modal-columns">
              <article className="panel-card">
                <div className="panel-head">
                  <h4>분석 메모</h4>
                  <span className="status-pill">{result.analysisGroup}</span>
                </div>
                <ul className="summary-list">
                  {result.highlights.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                  <li>가용 연도: {result.availableYears.join(", ")}</li>
                  <li>데이터 소스: {result.source}</li>
                </ul>
              </article>

              <article className="panel-card">
                <div className="panel-head">
                  <h4>주의사항</h4>
                  <span className="status-pill muted">{result.warnings.length}건</span>
                </div>
                {result.warnings.length ? (
                  <ul className="warning-list">
                    {result.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : (
                  <p>탐지된 주요 경고는 없습니다.</p>
                )}
              </article>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
