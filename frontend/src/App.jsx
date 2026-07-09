import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  fetchAnomalyAnalysis,
  fetchCompanyProfile,
  fetchCompanySearch,
  fetchLiquidityMetric,
  fetchResolvedCompany,
} from "./api";

const analysisTabs = [
  { code: "liquidity_risk", label: "현금화 리스크 분석", ready: true },
  { code: "growth", label: "성장성 분석", ready: false },
  { code: "dev_inventory_provision", label: "개발비·재고·충당부채 리스크 분석", ready: false },
  { code: "anomaly", label: "이상징후 분석", ready: true },
];

const liquidityMetrics = [
  { code: "revenue_growth", name: "매출액 증가율", description: "외형 성장" },
  { code: "operating_margin", name: "영업이익률", description: "본업 수익성" },
  { code: "cfo_conversion", name: "영업활동현금흐름 전환율", description: "이익의 현금화 수준" },
  { code: "contract_asset_ratio", name: "계약자산비율", description: "미청구·미회수 성격의 부담" },
  { code: "net_contract_asset_ratio", name: "순계약자산비율", description: "수익인식과 청구 간 괴리" },
];

function formatCompactNumber(value) {
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

function LineChart({ points, valueKey, compareKey, unitLabel }) {
  const companyValues = points.map((point) => point[valueKey]).filter((value) => value != null);
  const averageValues = points.map((point) => point[compareKey]).filter((value) => value != null);
  const allValues = [...companyValues, ...averageValues];

  if (!allValues.length) {
    return <div className="chart-empty">표시할 시계열 데이터가 없습니다.</div>;
  }

  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = maxValue - minValue || 1;

  function buildPath(targetKey) {
    return points
      .map((point, index) => {
        const value = point[targetKey];
        const x = (index / Math.max(points.length - 1, 1)) * 100;
        const y = value == null ? 50 : 100 - ((value - minValue) / range) * 100;
        return `${x},${y}`;
      })
      .join(" ");
  }

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <strong>5개년 추이</strong>
          <span>{unitLabel}</span>
        </div>
        <div className="chart-legend">
          <span className="legend-item">
            <i className="legend-dot company" />
            기업
          </span>
          <span className="legend-item">
            <i className="legend-dot average" />
            비교 평균
          </span>
        </div>
      </div>
      <svg className="metric-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polyline className="metric-line average" fill="none" points={buildPath(compareKey)} />
        <polyline className="metric-line company" fill="none" points={buildPath(valueKey)} />
      </svg>
      <div className="chart-years">
        {points.map((point) => (
          <div key={point.year}>
            <strong>{point.year}</strong>
            <span>n={point.sampleSize}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SearchSuggestions({ items, onSelect }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="suggestion-box">
      {items.map((item) => (
        <button key={item.companyId} className="suggestion-item" onClick={() => onSelect(item)} type="button">
          <div>
            <strong>{item.companyName}</strong>
            <span>{item.stockCode}</span>
          </div>
          <em>{item.companyId}</em>
        </button>
      ))}
    </div>
  );
}

function MetricsSelector({ selectedMetric, onSelect }) {
  return (
    <div className="metric-selector">
      {liquidityMetrics.map((metric) => (
        <button
          key={metric.code}
          className={`metric-chip ${selectedMetric === metric.code ? "active" : ""}`}
          onClick={() => onSelect(metric.code)}
          type="button"
        >
          <strong>{metric.name}</strong>
          <span>{metric.description}</span>
        </button>
      ))}
    </div>
  );
}

function DetailTable({ details }) {
  return (
    <div className="detail-table">
      {details.map((detail) => (
        <div key={detail.label} className="detail-row">
          <strong>{detail.label}</strong>
          <span>{detail.currentDisplay}</span>
          <span>{detail.previousDisplay}</span>
          <em>{detail.note || ""}</em>
        </div>
      ))}
    </div>
  );
}

function LiquidityPanel({
  metricData,
  groupScope,
  onGroupScopeChange,
  selectedMetric,
  onSelectMetric,
  showDetails,
  onToggleDetails,
  isLoading,
}) {
  const activeMetric = useMemo(
    () => liquidityMetrics.find((metric) => metric.code === selectedMetric),
    [selectedMetric],
  );

  return (
    <div className="analysis-panel">
      <div className="panel-toolbar">
        <div>
          <p className="eyebrow">지표 선택</p>
          <h4>현금화 리스크 지표</h4>
        </div>
        <label className="scope-select">
          <span>비교 평균</span>
          <select value={groupScope} onChange={(event) => onGroupScopeChange(event.target.value)}>
            <option value="A">A 그룹</option>
            <option value="AB">A+B 그룹</option>
            <option value="ABC">A+B+C 그룹</option>
          </select>
        </label>
      </div>

      <MetricsSelector selectedMetric={selectedMetric} onSelect={onSelectMetric} />

      {isLoading ? <div className="loading-panel">분석 데이터를 계산하는 중입니다.</div> : null}

      {!isLoading && metricData ? (
        <>
          <div className="metric-hero">
            <div className="metric-hero-card emphasis">
              <span>{activeMetric?.name}</span>
              <strong>{metricData.currentDisplay}</strong>
              <em>{metricData.sourceLabel}</em>
            </div>
            <div className="metric-hero-card">
              <span>{groupScope} 평균</span>
              <strong>{metricData.averageDisplay}</strong>
              <em>표본 {metricData.averageSampleSize}개</em>
            </div>
            <div className="metric-hero-card">
              <span>지표 의미</span>
              <strong>{activeMetric?.description}</strong>
              <em>당기 기준: 2025년</em>
            </div>
          </div>

          {metricData.currentReason ? <div className="status-banner warning">{metricData.currentReason}</div> : null}

          <div className="panel-inline-actions">
            <button className="ghost-button" onClick={onToggleDetails} type="button">
              {showDetails ? "상세정보 닫기" : "상세정보"}
            </button>
          </div>

          <LineChart
            compareKey="averageValue"
            points={metricData.series}
            unitLabel={selectedMetric === "cfo_conversion" ? "배수" : "퍼센트"}
            valueKey="companyValue"
          />

          {showDetails ? <DetailTable details={metricData.details} /> : null}
        </>
      ) : null}
    </div>
  );
}

function AnomalyPanel({ anomalyData, isLoading }) {
  if (isLoading) {
    return <div className="loading-panel">이상징후를 판별하는 중입니다.</div>;
  }

  if (!anomalyData) {
    return null;
  }

  return (
    <div className="analysis-panel">
      <div className="metric-hero">
        <div className={`metric-hero-card emphasis severity-${anomalyData.overallRiskLevel}`}>
          <span>종합 등급</span>
          <strong>{anomalyData.overallRiskLevel}</strong>
          <em>{anomalyData.sourceLabel}</em>
        </div>
        <div className="metric-hero-card">
          <span>핵심 해석</span>
          <strong>{anomalyData.overallSummary}</strong>
          <em>{anomalyData.note || "추가 제한사항 없음"}</em>
        </div>
      </div>

      <div className="indicator-grid">
        {anomalyData.indicators.map((indicator) => (
          <article key={indicator.label} className="indicator-card">
            <span>{indicator.label}</span>
            <strong>{indicator.display}</strong>
            <em>{indicator.description}</em>
          </article>
        ))}
      </div>

      <div className="signal-stack">
        {anomalyData.signals.map((signal) => (
          <article key={signal.code} className={`signal-card ${signal.triggered ? "triggered" : ""}`}>
            <div className="signal-head">
              <strong>{signal.title}</strong>
              <span>{signal.severity}</span>
            </div>
            <p>{signal.summary}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

function AnalysisModal({
  profile,
  activeTab,
  onTabChange,
  onClose,
  selectedMetric,
  onSelectMetric,
  groupScope,
  onGroupScopeChange,
  metricData,
  anomalyData,
  isMetricLoading,
  isAnomalyLoading,
  showDetails,
  onToggleDetails,
}) {
  if (!profile) {
    return null;
  }

  const primaryGroup = profile.groups[0];

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <section className="analysis-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-header">
          <div>
            <p className="eyebrow">방산기업 현금화 리스크 분석</p>
            <h2>{profile.company.corp_name}</h2>
            <p className="modal-subtitle">
              {profile.company.stock_code} · {profile.company.corp_code}
              {primaryGroup ? ` · ${primaryGroup.industry_id.toUpperCase()}-${primaryGroup.level}` : ""}
            </p>
          </div>
          <button className="close-button" onClick={onClose} type="button">
            닫기
          </button>
        </header>

        <div className="tab-row">
          {analysisTabs.map((tab) => (
            <button
              key={tab.code}
              className={`tab-button ${activeTab === tab.code ? "active" : ""}`}
              onClick={() => onTabChange(tab.code)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "liquidity_risk" ? (
          <LiquidityPanel
            groupScope={groupScope}
            isLoading={isMetricLoading}
            metricData={metricData}
            onGroupScopeChange={onGroupScopeChange}
            onSelectMetric={onSelectMetric}
            onToggleDetails={onToggleDetails}
            selectedMetric={selectedMetric}
            showDetails={showDetails}
          />
        ) : null}

        {activeTab === "anomaly" ? <AnomalyPanel anomalyData={anomalyData} isLoading={isAnomalyLoading} /> : null}

        {activeTab === "growth" || activeTab === "dev_inventory_provision" ? (
          <div className="coming-soon-panel">
            <strong>준비 중</strong>
            <span>해당 분석은 현재 구조 개편 후 순차적으로 연결할 예정입니다.</span>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function App() {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [profile, setProfile] = useState(null);
  const [activeTab, setActiveTab] = useState("liquidity_risk");
  const [selectedMetric, setSelectedMetric] = useState("revenue_growth");
  const [groupScope, setGroupScope] = useState("A");
  const [metricData, setMetricData] = useState(null);
  const [anomalyData, setAnomalyData] = useState(null);
  const [isMetricLoading, setIsMetricLoading] = useState(false);
  const [isAnomalyLoading, setIsAnomalyLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (!deferredQuery.trim() || !showSuggestions) {
      setSuggestions([]);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const items = await fetchCompanySearch(deferredQuery);
        if (!cancelled) {
          setSuggestions(items);
        }
      } catch {
        if (!cancelled) {
          setSuggestions([]);
        }
      } finally {
        if (!cancelled) {
          setIsSearching(false);
        }
      }
    }, 160);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [deferredQuery, showSuggestions]);

  useEffect(() => {
    if (!profile || activeTab !== "liquidity_risk") {
      return;
    }

    let cancelled = false;
    setIsMetricLoading(true);
    setShowDetails(false);

    fetchLiquidityMetric(profile.company.corp_code, selectedMetric, groupScope)
      .then((data) => {
        if (!cancelled) {
          setMetricData(data);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setMetricData(null);
          setError(caught instanceof Error ? caught.message : "현금화 리스크 분석을 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsMetricLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, groupScope, profile, selectedMetric]);

  useEffect(() => {
    if (!profile || activeTab !== "anomaly") {
      return;
    }

    let cancelled = false;
    setIsAnomalyLoading(true);

    fetchAnomalyAnalysis(profile.company.corp_code, groupScope)
      .then((data) => {
        if (!cancelled) {
          setAnomalyData(data);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setAnomalyData(null);
          setError(caught instanceof Error ? caught.message : "이상징후 분석을 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsAnomalyLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, groupScope, profile]);

  async function openCompanyProfileFromSuggestion(item) {
    setError("");
    setIsResolving(true);
    try {
      const data = await fetchCompanyProfile(item.companyId);
      setProfile(data);
      setActiveTab("liquidity_risk");
      setGroupScope("A");
      setSelectedMetric("revenue_growth");
      setQuery(item.companyName);
      setSuggestions([]);
      setShowSuggestions(false);
    } catch (caught) {
      setProfile(null);
      setError(caught instanceof Error ? caught.message : "기업 정보를 불러오지 못했습니다.");
    } finally {
      setIsResolving(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      return;
    }

    setError("");
    setIsResolving(true);
    try {
      const data = await fetchResolvedCompany(normalized);
      setProfile(data);
      setActiveTab("liquidity_risk");
      setGroupScope("A");
      setSelectedMetric("revenue_growth");
      setSuggestions([]);
      setShowSuggestions(false);
    } catch (caught) {
      setProfile(null);
      setError(caught instanceof Error ? caught.message : "해당 기업정보가 존재하지 않습니다.");
    } finally {
      setIsResolving(false);
    }
  }

  function closeModal() {
    setProfile(null);
    setMetricData(null);
    setAnomalyData(null);
    setShowDetails(false);
  }

  return (
    <div className="app-shell">
      <main className="landing">
        <section className="hero-panel">
          <p className="hero-kicker">Defense Cash Conversion Risk Console</p>
          <h1>기업명, 종목코드, 기업코드로 바로 찾고 2025년 현금화 리스크를 읽는다.</h1>
          <p className="hero-copy">
            검색 후 모달에서 현금화 리스크, 이상징후, 비교 그룹 평균과 5개년 추이를 한 번에 확인할 수 있다.
          </p>

          <form className="search-shell" onSubmit={handleSubmit}>
            <div className="search-field">
              <input
                placeholder="예: 한화에어로스페이스 / 012450 / 00126566"
                type="text"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => {
                  if (query.trim()) {
                    setShowSuggestions(true);
                  }
                }}
              />
              <SearchSuggestions items={suggestions} onSelect={openCompanyProfileFromSuggestion} />
            </div>
            <button className="search-button" disabled={isResolving} type="submit">
              {isResolving ? "검색 중" : "검색"}
            </button>
          </form>

          <div className="hero-hints">
            <span>자동완성 클릭 시 바로 분석 모달 오픈</span>
            <span>정확히 일치하는 기업명·종목코드·기업코드는 엔터만으로 검색</span>
            <span>{isSearching ? "후보 기업 검색 중" : "기준 데이터: companies_basic"}</span>
          </div>
        </section>

        <section className="info-strip">
          <article>
            <span>당기 기준</span>
            <strong>2025년 고정</strong>
          </article>
          <article>
            <span>재무제표 우선순위</span>
            <strong>CFS 우선, 없으면 OFS</strong>
          </article>
          <article>
            <span>비교 범위</span>
            <strong>A / AB / ABC 그룹</strong>
          </article>
        </section>

        {error ? <div className="status-banner error">{error}</div> : null}
      </main>

      <AnalysisModal
        activeTab={activeTab}
        anomalyData={anomalyData}
        groupScope={groupScope}
        isAnomalyLoading={isAnomalyLoading}
        isMetricLoading={isMetricLoading}
        metricData={metricData}
        onClose={closeModal}
        onGroupScopeChange={setGroupScope}
        onSelectMetric={setSelectedMetric}
        onTabChange={setActiveTab}
        onToggleDetails={() => setShowDetails((current) => !current)}
        profile={profile}
        selectedMetric={selectedMetric}
        showDetails={showDetails}
      />
    </div>
  );
}

export default App;
