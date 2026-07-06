import { useState } from "react";

import { fetchDebtRatio } from "./api";

const recentQueries = ["삼성전자", "SK하이닉스", "00126380"];

function formatCurrency(value) {
  return `${new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 0,
  }).format(value)}원`;
}

function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleAnalyze(nextQuery) {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setError("기업명 또는 기업번호를 입력해 주세요.");
      setResult(null);
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const data = await fetchDebtRatio(trimmed);
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
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="brand-mark">AuditRisk-AI</p>
          <p className="brand-sub">Precision Analytics</p>
        </div>
        <nav className="sidebar-nav">
          <a className="nav-item active" href="#overview">Overview</a>
          <a className="nav-item" href="#results">Financials</a>
          <a className="nav-item" href="#results">Risk Analysis</a>
          <a className="nav-item" href="#results">Documents</a>
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Analytics</p>
            <h1>DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스</h1>
          </div>
          <div className="topbar-badge">MVP / Debt Ratio</div>
        </header>

        <section className="hero-card" id="overview">
          <div className="hero-copy">
            <p className="eyebrow">Corporate Risk Analysis</p>
            <h2>기업명을 입력하면 DART 재무제표를 바탕으로 부채비율을 분석합니다.</h2>
            <p>
              기업명을 입력하면 DART 재무제표 데이터를 기반으로 주요 재무비율과 감사위험 분석
              결과를 제공합니다. MVP 단계에서는 부채비율 분석을 제공합니다.
            </p>
          </div>

          <div className="search-card">
            <label className="search-label" htmlFor="corp-query">
              기업명 또는 기업번호
            </label>
            <div className="search-row">
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
              <button disabled={isLoading} onClick={() => handleAnalyze(query)} type="button">
                {isLoading ? "분석 중..." : "분석하기"}
              </button>
            </div>
            <div className="recent-list">
              <span>최근 예시</span>
              {recentQueries.map((item) => (
                <button
                  key={item}
                  className="recent-chip"
                  onClick={() => {
                    setQuery(item);
                    handleAnalyze(item);
                  }}
                  type="button"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="results-section" id="results">
          {error ? (
            <div className="message-card error-card">
              <p className="message-title">분석을 완료하지 못했습니다.</p>
              <p>{error}</p>
            </div>
          ) : null}

          {isLoading ? (
            <div className="message-card loading-card">
              <p className="message-title">DART 데이터를 조회하고 있습니다.</p>
              <p>기업 검색, 재무제표 조회, 부채비율 계산을 순차적으로 진행 중입니다.</p>
            </div>
          ) : null}

          {result ? (
            <>
              <div className="results-head">
                <div>
                  <p className="eyebrow">Analysis Result</p>
                  <h3>{result.corpName}</h3>
                  <p className="corp-code">DART: {result.corpCode}</p>
                </div>
                <div className="year-chip">대상연도 {result.year}</div>
              </div>

              <div className="primary-grid">
                <article className="data-card hero-metric">
                  <span>부채비율</span>
                  <strong>{result.debtRatio}%</strong>
                  <p>부채비율 = 부채 / 자본 × 100</p>
                </article>

                <article className="data-card">
                  <span>부채</span>
                  <strong>{formatCurrency(result.liabilities)}</strong>
                </article>

                <article className="data-card">
                  <span>자본</span>
                  <strong>{formatCurrency(result.equity)}</strong>
                </article>

                <article className="data-card">
                  <span>데이터 출처</span>
                  <strong>{result.source}</strong>
                  <p>{result.cached ? "캐시 사용됨" : "실시간 조회"}</p>
                </article>
              </div>

              <div className="secondary-grid">
                <article className="panel-card">
                  <div className="panel-head">
                    <h4>분석 요약</h4>
                    <span className="status-pill">{result.cached ? "Cached" : "Live"}</span>
                  </div>
                  <p>
                    {result.corpName}의 {result.year}년 기준 재무상태표에서 부채와 자본을 추출해
                    부채비율을 계산했습니다.
                  </p>
                  <ul className="summary-list">
                    <li>기업번호: {result.corpCode}</li>
                    <li>부채: {formatCurrency(result.liabilities)}</li>
                    <li>자본: {formatCurrency(result.equity)}</li>
                  </ul>
                </article>

                <article className="panel-card">
                  <div className="panel-head">
                    <h4>Warnings</h4>
                    <span className="status-pill muted">{result.warnings.length}건</span>
                  </div>
                  {result.warnings.length ? (
                    <ul className="warning-list">
                      {result.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>추가 warning 없이 기본 분석을 완료했습니다.</p>
                  )}
                </article>
              </div>
            </>
          ) : !isLoading && !error ? (
            <div className="message-card idle-card">
              <p className="message-title">아직 분석 결과가 없습니다.</p>
              <p>기업명 또는 기업번호를 입력하고 분석 버튼을 눌러 주세요.</p>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

export default App;
