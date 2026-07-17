import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  fetchAnomalyAnalysis,
  fetchCompanyProfile,
  fetchCompanySearch,
  fetchIndustryComparison,
  fetchIndustries,
  fetchLiquidityMetric,
  fetchResolvedCompany,
} from "./api";

const analysisTabs = [
  { code: "liquidity_risk", label: "현금화 리스크 분석", ready: true },
  { code: "growth", label: "성장성 분석", ready: false },
  { code: "dev_inventory_provision", label: "개발비·재고·충당부채 리스크 분석", ready: false },
  { code: "anomaly", label: "이상징후 분석", ready: true },
];

const industryLabels = {
  defense: "방산",
  semiconductor: "반도체",
  construction: "건설",
};

function uniqueIndustries(groups) {
  const seen = new Map();
  groups.forEach((group) => {
    if (!seen.has(group.industry_id)) {
      seen.set(group.industry_id, group);
    }
  });
  return [...seen.values()];
}

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

function formatTooltipValue(value, metricCode) {
  if (value == null) {
    return "N/A";
  }
  if (metricCode === "cfo_conversion") {
    return `${value.toFixed(2)}배`;
  }
  return `${value.toFixed(1)}%`;
}

function buildSegments(points, targetKey, minValue, range) {
  const segments = [];
  let current = [];

  points.forEach((point, index) => {
    const value = point[targetKey];
    if (value == null) {
      if (current.length > 1) {
        segments.push(current);
      }
      current = [];
      return;
    }

    const x = (index / Math.max(points.length - 1, 1)) * 100;
    const y = 100 - ((value - minValue) / range) * 100;
    current.push(`${x},${y}`);
  });

  if (current.length > 1) {
    segments.push(current);
  }

  return segments;
}

function LineChart({ points, valueKey, compareKey, unitLabel, metricCode, companyName }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const companyValues = points.map((point) => point[valueKey]).filter((value) => value != null);
  const averageValues = points.map((point) => point[compareKey]).filter((value) => value != null);
  const allValues = [...companyValues, ...averageValues];

  if (!allValues.length) {
    return <div className="chart-empty">표시할 시계열 데이터가 없습니다.</div>;
  }

  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = maxValue - minValue || 1;
  const companySegments = buildSegments(points, valueKey, minValue, range);
  const averageSegments = buildSegments(points, compareKey, minValue, range);
  const hoveredPoint = hoveredIndex == null ? null : points[hoveredIndex];

  function yForValue(value) {
    if (value == null) {
      return null;
    }
    return 100 - ((value - minValue) / range) * 100;
  }

  function handlePointerMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = event.clientX - rect.left;
    const width = rect.width || 1;
    const ratio = Math.min(Math.max(relativeX / width, 0), 1);
    const index = Math.round(ratio * Math.max(points.length - 1, 1));
    setHoveredIndex(index);
    setTooltipPosition({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
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
      <div className="chart-stage">
        <svg
          className="metric-chart"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
          onMouseMove={handlePointerMove}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          {averageSegments.map((segment, index) => (
            <polyline key={`avg-${index}`} className="metric-line average" fill="none" points={segment.join(" ")} />
          ))}
          {companySegments.map((segment, index) => (
            <polyline key={`company-${index}`} className="metric-line company" fill="none" points={segment.join(" ")} />
          ))}
          {points.map((point, index) => {
            const x = (index / Math.max(points.length - 1, 1)) * 100;
            const companyY = yForValue(point.companyValue);
            const averageY = yForValue(point.averageValue);
            return (
              <g key={point.year}>
                {companyY != null ? <circle className="chart-dot company" cx={x} cy={companyY} r="1.4" /> : null}
                {averageY != null ? <circle className="chart-dot average" cx={x} cy={averageY} r="1.4" /> : null}
              </g>
            );
          })}
        </svg>
        {hoveredPoint ? (
          <div
            className="chart-tooltip floating"
            style={{
              left: `${Math.min(Math.max(tooltipPosition.x + 14, 12), 720)}px`,
              top: `${Math.max(tooltipPosition.y - 18, 12)}px`,
            }}
          >
            <strong>{hoveredPoint.year}</strong>
            <span>
              {companyName}: {formatTooltipValue(hoveredPoint.companyValue, metricCode)}
            </span>
            <span>산업평균: {formatTooltipValue(hoveredPoint.averageValue, metricCode)}</span>
            <em>표본 {hoveredPoint.sampleSize}개</em>
          </div>
        ) : null}
      </div>
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

function formatComparisonValue(value, definition) {
  if (value == null) {
    return "N/A";
  }
  if (definition.unit === "KRW") {
    return formatCompactNumber(value);
  }
  if (definition.unit === "%") {
    return `${value.toFixed(1)}%`;
  }
  return `${value.toFixed(2)}배`;
}

function IndustryComparisonTable({ comparison, onClose }) {
  const [sortCode, setSortCode] = useState("revenue");
  const [sortDirection, setSortDirection] = useState("desc");
  const definitions = comparison.metricDefinitions;
  const sortedRows = [...comparison.rows].sort((left, right) => {
    const leftValue = left.metrics[sortCode] ?? Number.NEGATIVE_INFINITY;
    const rightValue = right.metrics[sortCode] ?? Number.NEGATIVE_INFINITY;
    return sortDirection === "desc" ? rightValue - leftValue : leftValue - rightValue;
  });

  function selectSort(code) {
    if (code === sortCode) {
      setSortDirection((current) => current === "desc" ? "asc" : "desc");
    } else {
      setSortCode(code);
      setSortDirection("desc");
    }
  }

  return (
    <section className="comparison-section">
      <div className="comparison-head">
        <div>
          <p className="eyebrow">산업 비교 · {comparison.year}</p>
          <h2>반도체 기업 비교</h2>
          <p>연결(CFS) 우선으로 수집하며, 값이 없을 경우 별도(OFS) 기준을 사용합니다.</p>
        </div>
        <button className="ghost-button" onClick={onClose} type="button">산업 목록으로</button>
      </div>
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>기업</th>
              <th>기준</th>
              <th>데이터</th>
              {definitions.map((definition) => (
                <th key={definition.code}>
                  <button onClick={() => selectSort(definition.code)} type="button">
                    {definition.label} {sortCode === definition.code ? (sortDirection === "desc" ? "↓" : "↑") : "↕"}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr key={row.corpCode}>
                <td><strong>{row.corpName}</strong><span>{row.stockCode}</span></td>
                <td>{row.basis || "N/A"}</td>
                <td>{row.completeness}/{row.requiredAccountCount}</td>
                {definitions.map((definition) => <td key={definition.code}>{formatComparisonValue(row.metrics[definition.code], definition)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function IndustryLanding({ industries, isLoading, onSelectCompanyAnalysis }) {
  const [comparison, setComparison] = useState(null);
  const [isComparisonLoading, setIsComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState("");

  async function openComparison(industryId) {
    if (industryId !== "semiconductor") {
      setComparisonError("이 산업의 비교 테이블은 준비 중입니다. 현재는 기업 수와 데이터 준비 상태만 확인할 수 있습니다.");
      return;
    }
    setComparisonError("");
    setIsComparisonLoading(true);
    try {
      setComparison(await fetchIndustryComparison(industryId));
    } catch (caught) {
      setComparisonError(caught instanceof Error ? caught.message : "산업 비교 데이터를 불러오지 못했습니다.");
    } finally {
      setIsComparisonLoading(false);
    }
  }

  if (isLoading) {
    return <div className="loading-panel">산업 커버리지를 불러오는 중입니다.</div>;
  }

  if (isComparisonLoading) {
    return <div className="loading-panel">반도체 기업 비교를 계산하는 중입니다.</div>;
  }

  if (comparison) {
    return <IndustryComparisonTable comparison={comparison} onClose={() => setComparison(null)} />;
  }

  return (
    <section className="industry-landing">
      <div className="industry-landing-head">
        <div>
          <p className="eyebrow">산업 커버리지</p>
          <h1>분석할 산업을 먼저 이해하세요.</h1>
        </div>
        <p>현재 제공 범위와 비교그룹 상태를 확인한 뒤, 기업 분석으로 이동할 수 있습니다.</p>
      </div>
      <div className="industry-card-grid">
        {industries.map((industry) => {
          const ready = industry.analysisStatus === "ready";
          return (
            <article className="industry-card" key={industry.industryId}>
              <div className="industry-card-top">
                <span>{industryLabels[industry.industryId] || industry.industryId.toUpperCase()}</span>
                <em className={ready ? "ready" : "prepared"}>{ready ? "분석 가능" : "데이터 준비"}</em>
              </div>
              <strong>{industry.companyCount}개 기업</strong>
              <p>
                A/B/C 비교그룹 분류 {industry.classifiedCompanyCount}개 · 데이터 기준일 {industry.updatedAt || "확인 중"}
              </p>
              {ready ? <div className="industry-themes">{industry.availableThemes.map((theme) => <span key={theme}>{theme}</span>)}</div> : null}
              <button className="ghost-button" onClick={() => ready ? onSelectCompanyAnalysis() : openComparison(industry.industryId)} type="button">
                {ready ? "기업 분석으로 이동" : industry.industryId === "semiconductor" ? "기업 비교 보기" : "준비 상태 보기"}
              </button>
            </article>
          );
        })}
      </div>
      {comparisonError ? <div className="status-banner warning">{comparisonError}</div> : null}
    </section>
  );
}

function IndustryPickerModal({ profile, onSelect, onClose }) {
  if (!profile) {
    return null;
  }

  const industries = uniqueIndustries(profile.groups);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <section className="industry-picker-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <header className="picker-header">
          <div>
            <p className="eyebrow">분석 산업 선택</p>
            <h3>{profile.company.corp_name}</h3>
          </div>
          <button className="close-button" onClick={onClose} type="button">
            닫기
          </button>
        </header>
        <div className="industry-option-list">
          {industries.map((industry) => (
            <button
              key={industry.industry_id}
              className="industry-option"
              onClick={() => onSelect(industry.industry_id)}
              type="button"
            >
              <strong>{industry.industry_id.toUpperCase()}</strong>
              <span>
                {industry.level} 그룹
                {industry.level_category ? ` · ${industry.level_category}` : ""}
              </span>
            </button>
          ))}
        </div>
      </section>
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

function DetailTable({ details, averageMembers, averageCoverageYears, averageSampleSize }) {
  return (
    <div className="detail-stack">
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

      <div className="average-detail-card">
        <div className="average-detail-head">
          <strong>평균 계산 사용 표본</strong>
          <span>
            {averageCoverageYears.join(", ")} 전 기간 존재 기업 {averageSampleSize}개
          </span>
        </div>
        <div className="average-member-list">
          {averageMembers.map((member) => (
            <article key={member.corpCode} className="average-member">
              <div className="average-member-head">
                <strong>{member.corpName}</strong>
                <span>{member.metricDisplay}</span>
              </div>
              <em>{member.sourceLabel}</em>
              <div className="average-account-grid">
                {member.accounts.map((account) => (
                  <div key={`${member.corpCode}-${account.accountName}`} className="average-account">
                    <strong>{account.accountName}</strong>
                    <span>{account.currentDisplay}</span>
                    <span>{account.previousDisplay}</span>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function EvidencePanel({ metricData, metricCode, showDetails, onToggleDetails }) {
  const distribution = metricData.peerDistribution;
  const distributionItems = [
    ["최저", distribution?.minimum],
    ["1사분위", distribution?.firstQuartile],
    ["중앙값", distribution?.median],
    ["3사분위", distribution?.thirdQuartile],
    ["최고", distribution?.maximum],
  ];

  return (
    <section className="evidence-panel">
      <div className="evidence-head">
        <div>
          <p className="eyebrow">근거와 비교 기준</p>
          <h5>결론 전에 확인할 정보</h5>
        </div>
        <button className="ghost-button" onClick={onToggleDetails} type="button">
          {showDetails ? "원천 계정 닫기" : "원천 계정 보기"}
        </button>
      </div>

      <div className="evidence-grid">
        <article className="evidence-card">
          <span>동종 분포 내 위치</span>
          <strong>{distribution?.companyPercentile == null ? "계산 불가" : `${distribution.companyPercentile.toFixed(0)} 백분위`}</strong>
          <p>표본 {distribution?.sampleSize ?? 0}개 · 값의 크기만 비교한 위치입니다.</p>
        </article>
        <article className="evidence-card">
          <span>산식과 기준</span>
          <strong>{metricData.metricDescription}</strong>
          <p>{metricData.formula} · {metricData.sourceLabel}</p>
        </article>
        <article className="evidence-card">
          <span>해석 제한사항</span>
          <strong>{metricData.currentReason || "특이 제한사항 없음"}</strong>
          <p>{distribution?.note}</p>
        </article>
      </div>

      <div className="distribution-row" aria-label="동종 기업 분포">
        {distributionItems.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{formatTooltipValue(value, metricCode)}</strong>
          </div>
        ))}
      </div>
    </section>
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

          <LineChart
            compareKey="averageValue"
            companyName={metricData.company.corp_name}
            metricCode={selectedMetric}
            points={metricData.series}
            unitLabel={selectedMetric === "cfo_conversion" ? "배수" : "퍼센트"}
            valueKey="companyValue"
          />

          <EvidencePanel
            metricCode={selectedMetric}
            metricData={metricData}
            onToggleDetails={onToggleDetails}
            showDetails={showDetails}
          />

          {showDetails ? (
            <DetailTable
              averageCoverageYears={metricData.averageCoverageYears}
              averageMembers={metricData.averageMembers}
              averageSampleSize={metricData.averageSampleSize}
              details={metricData.details}
            />
          ) : null}
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

function AnalysisGuide({ groupScope, metricData, primaryGroup }) {
  return (
    <section className="analysis-guide" aria-label="분석 읽는 방법">
      <div className="guide-intro">
        <p className="eyebrow">분석 읽는 방법</p>
        <strong>숫자 → 동종 비교 → 근거 계정 순으로 확인하세요.</strong>
      </div>
      <div className="guide-step">
        <span>01</span>
        <strong>분석 기준</strong>
        <p>{primaryGroup?.industry_id?.toUpperCase() || "산업"} · {groupScope} 그룹 · 2025년 기준</p>
      </div>
      <div className="guide-step">
        <span>02</span>
        <strong>비교 해석</strong>
        <p>{metricData ? `동일 기준 표본 ${metricData.averageSampleSize}개와 비교합니다.` : "지표를 불러오면 비교 표본을 표시합니다."}</p>
      </div>
      <div className="guide-step">
        <span>03</span>
        <strong>결론 전 확인</strong>
        <p>상세정보에서 계정값·출처·결측 제한사항을 확인하세요.</p>
      </div>
    </section>
  );
}

function ReviewDesk({ profile, selectedIndustryId, activeTab, metricData }) {
  const storageKey = `ari:review-note:${profile.company.corp_code}:${selectedIndustryId}:${activeTab}`;
  const [note, setNote] = useState("");
  const [shareStatus, setShareStatus] = useState("");

  useEffect(() => {
    setNote(window.localStorage.getItem(storageKey) || "");
    setShareStatus("");
  }, [storageKey]);

  function updateNote(value) {
    setNote(value);
    window.localStorage.setItem(storageKey, value);
  }

  async function copyAnalysisLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShareStatus("현재 분석 주소를 복사했습니다.");
    } catch {
      setShareStatus("주소 복사를 허용해 주세요. 브라우저 주소창의 URL을 직접 복사할 수 있습니다.");
    }
  }

  return (
    <section className="review-desk" aria-label="검토 메모와 리포트">
      <div className="review-head">
        <div>
          <p className="eyebrow">검토 메모와 리포트</p>
          <h5>{metricData ? `${metricData.metricName} 검토 메모` : "분석 검토 메모"}</h5>
        </div>
        <div className="review-actions">
          <button className="ghost-button" onClick={copyAnalysisLink} type="button">분석 링크 복사</button>
          <button className="print-button" onClick={() => window.print()} type="button">인쇄용 리포트</button>
        </div>
      </div>
      <textarea
        aria-label="검토 메모"
        onChange={(event) => updateNote(event.target.value)}
        placeholder="검토한 사실, 추가 확인할 공시·계정, 담당자 의견을 기록하세요. 이 메모는 현재 브라우저에만 저장됩니다."
        value={note}
      />
      <div className="review-foot">
        <span>기업 · 산업 · 분석 탭별로 이 브라우저에 자동 저장됩니다.</span>
        {shareStatus ? <strong>{shareStatus}</strong> : null}
      </div>
    </section>
  );
}

function AnalysisWorkspace({
  profile,
  selectedIndustryId,
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

  const primaryGroup = profile.groups.find((group) => group.industry_id === selectedIndustryId) || profile.groups[0];
  const isDefenseWorkspace = selectedIndustryId === "defense";

  return (
    <section className="analysis-workspace">
      <header className="workspace-header">
          <div>
            <p className="eyebrow">기업 리스크 워크스페이스</p>
            <h2>{profile.company.corp_name}</h2>
            <p className="modal-subtitle">
              {profile.company.stock_code} · {profile.company.corp_code}
              {primaryGroup ? ` · ${primaryGroup.industry_id.toUpperCase()}-${primaryGroup.level}` : ""}
            </p>
          </div>
          <div className="workspace-context">
            <span>기준연도 2025</span>
            <span>비교군 {groupScope}</span>
            <button className="close-button" onClick={onClose} type="button">
              분석 종료
            </button>
          </div>
      </header>

      <AnalysisGuide groupScope={groupScope} metricData={metricData} primaryGroup={primaryGroup} />

      {isDefenseWorkspace ? (
        <ReviewDesk
          activeTab={activeTab || "overview"}
          metricData={metricData}
          profile={profile}
          selectedIndustryId={selectedIndustryId}
        />
      ) : null}

      {isDefenseWorkspace ? <div className="tab-row">
          {analysisTabs.map((tab) => (
            <button
              key={tab.code}
              className={`tab-button ${activeTab === tab.code ? "active" : ""}`}
              onClick={() => onTabChange(tab.code)}
              type="button"
            >
              <span>{tab.label}</span>
              <em className={`tab-status ${tab.ready ? "ready" : "planned"}`}>{tab.ready ? "사용 가능" : "준비 중"}</em>
            </button>
          ))}
        </div> : null}

        {!isDefenseWorkspace ? (
          <div className="coming-soon-panel">
            <strong>{selectedIndustryId?.toUpperCase() || "산업"} 분석 준비 중</strong>
            <span>기업·산업 컨텍스트는 열렸습니다. 비교군 정책과 산업별 위험 규칙이 완료되면 이 워크스페이스에 연결됩니다.</span>
          </div>
        ) : null}

        {isDefenseWorkspace && !activeTab ? (
          <div className="empty-analysis-panel">
            <strong>분석을 시작해보세요</strong>
          </div>
        ) : null}

        {isDefenseWorkspace && activeTab === "liquidity_risk" ? (
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

        {isDefenseWorkspace && activeTab === "anomaly" ? <AnomalyPanel anomalyData={anomalyData} isLoading={isAnomalyLoading} /> : null}

        {isDefenseWorkspace && (activeTab === "growth" || activeTab === "dev_inventory_provision") ? (
          <div className="coming-soon-panel">
            <strong>준비 중</strong>
            <span>해당 분석은 현재 구조 개편 후 순차적으로 연결할 예정입니다.</span>
          </div>
        ) : null}
    </section>
  );
}

function App() {
  const [viewMode, setViewMode] = useState("stock");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [profile, setProfile] = useState(null);
  const [pendingProfile, setPendingProfile] = useState(null);
  const [selectedIndustryId, setSelectedIndustryId] = useState(null);
  const [activeTab, setActiveTab] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState("revenue_growth");
  const [groupScope, setGroupScope] = useState("A");
  const [metricData, setMetricData] = useState(null);
  const [anomalyData, setAnomalyData] = useState(null);
  const [isMetricLoading, setIsMetricLoading] = useState(false);
  const [isAnomalyLoading, setIsAnomalyLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [industries, setIndustries] = useState([]);
  const [isIndustriesLoading, setIsIndustriesLoading] = useState(false);

  function replaceLocation(path) {
    window.history.pushState({}, "", path);
  }

  function activateProfile(data, industryId) {
    setProfile(data);
    setSelectedIndustryId(industryId);
    setPendingProfile(null);
    setActiveTab("liquidity_risk");
    setGroupScope("A");
    setSelectedMetric("revenue_growth");
    setMetricData(null);
    setAnomalyData(null);
    setShowDetails(false);
    replaceLocation(`/companies/${encodeURIComponent(data.company.corp_code)}?industry=${encodeURIComponent(industryId || "")}`);
  }

  useEffect(() => {
    async function restoreWorkspace() {
      const match = window.location.pathname.match(/^\/companies\/([^/]+)$/);
      if (!match) {
        return;
      }

      setIsResolving(true);
      try {
        const data = await fetchCompanyProfile(decodeURIComponent(match[1]));
        const urlIndustry = new URLSearchParams(window.location.search).get("industry");
        const defaultIndustry = uniqueIndustries(data.groups).find((group) => group.industry_id === urlIndustry)?.industry_id
          || data.groups.find((group) => group.is_primary)?.industry_id
          || data.groups[0]?.industry_id
          || null;
        setProfile(data);
        setSelectedIndustryId(defaultIndustry);
        setActiveTab("liquidity_risk");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "기업 정보를 불러오지 못했습니다.");
      } finally {
        setIsResolving(false);
      }
    }

    restoreWorkspace();
    window.addEventListener("popstate", restoreWorkspace);
    return () => window.removeEventListener("popstate", restoreWorkspace);
  }, []);

  useEffect(() => {
    if (viewMode !== "industry" || industries.length) {
      return;
    }
    let cancelled = false;
    setIsIndustriesLoading(true);
    fetchIndustries()
      .then((data) => {
        if (!cancelled) {
          setIndustries(data);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "산업 데이터를 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsIndustriesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [industries.length, viewMode]);

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
    if (!profile || selectedIndustryId !== "defense" || activeTab !== "liquidity_risk") {
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
  }, [activeTab, groupScope, profile, selectedIndustryId, selectedMetric]);

  useEffect(() => {
    if (!profile || selectedIndustryId !== "defense" || activeTab !== "anomaly") {
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
  }, [activeTab, groupScope, profile, selectedIndustryId]);

  async function openCompanyProfileFromSuggestion(item) {
    setError("");
    setIsResolving(true);
    try {
      const data = await fetchCompanyProfile(item.companyId);
      const industries = uniqueIndustries(data.groups);
      if (industries.length > 1) {
        setPendingProfile(data);
      } else {
        activateProfile(data, industries[0]?.industry_id || null);
      }
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
      const industries = uniqueIndustries(data.groups);
      if (industries.length > 1) {
        setPendingProfile(data);
      } else {
        activateProfile(data, industries[0]?.industry_id || null);
      }
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
    setPendingProfile(null);
    setSelectedIndustryId(null);
    setActiveTab(null);
    setMetricData(null);
    setAnomalyData(null);
    setShowDetails(false);
    replaceLocation("/");
  }

  function handleIndustrySelect(industryId) {
    if (!pendingProfile) {
      return;
    }
    activateProfile(pendingProfile, industryId);
  }

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="brand-block">
          <span className="brand-mark">ARI</span>
          <strong>Audit Risk<br />Intelligence</strong>
          <p>산업별 재무 리스크 분석</p>
        </div>
        <button
          className={`side-link ${viewMode === "stock" ? "active" : ""}`}
          onClick={() => setViewMode("stock")}
          type="button"
        >
          <span>기업 분석</span>
          <em>기업별 리스크 워크스페이스</em>
        </button>
        <button
          className={`side-link ${viewMode === "industry" ? "active" : ""}`}
          onClick={() => setViewMode("industry")}
          type="button"
        >
          <span>산업 분석</span>
          <em>비교·스크리너 준비 중</em>
        </button>
      </aside>

      <div className="workspace-shell">
        <header className="top-search-bar">
          <div className="search-heading">
            <strong>분석할 기업 찾기</strong>
            <span>기업명, 종목코드 또는 법인코드를 입력하세요.</span>
          </div>
          <form className="search-shell compact" onSubmit={handleSubmit}>
            <div className="search-field">
              <input
                placeholder="기업명 / 종목코드 / 기업코드"
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
            <button className="search-button" disabled={isResolving || viewMode === "industry"} type="submit">
              {isResolving ? "검색 중" : "검색"}
            </button>
          </form>
        </header>

        <main className="content-stage">
          {viewMode === "stock" ? (
            <>
              {error ? <div className="status-banner error">{error}</div> : null}
              {isSearching ? <div className="search-status">검색 중</div> : null}
              {profile ? (
                <AnalysisWorkspace
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
                  selectedIndustryId={selectedIndustryId}
                  selectedMetric={selectedMetric}
                  showDetails={showDetails}
                />
              ) : (
                <div className="workspace-empty-state">
                  <p className="eyebrow">Audit Risk Intelligence</p>
                  <h1>기업을 선택해 산업별 리스크를 확인하세요.</h1>
                  <p>위 검색창에서 기업명, 종목코드 또는 법인코드를 입력하면 비교군과 근거 계정을 함께 분석합니다.</p>
                  <ol className="start-steps">
                    <li><span>1</span><div><strong>기업 선택</strong><p>검색 결과에서 분석 대상을 고릅니다.</p></div></li>
                    <li><span>2</span><div><strong>산업 기준 확인</strong><p>여러 산업에 속한 경우 비교할 산업을 선택합니다.</p></div></li>
                    <li><span>3</span><div><strong>근거까지 검토</strong><p>지표, 동종 비교, 원천 계정을 차례로 확인합니다.</p></div></li>
                  </ol>
                </div>
              )}
            </>
          ) : (
            <IndustryLanding
              industries={industries}
              isLoading={isIndustriesLoading}
              onSelectCompanyAnalysis={() => setViewMode("stock")}
            />
          )}
        </main>
      </div>

      <IndustryPickerModal
        onClose={() => setPendingProfile(null)}
        onSelect={handleIndustrySelect}
        profile={pendingProfile}
      />

    </div>
  );
}

export default App;
