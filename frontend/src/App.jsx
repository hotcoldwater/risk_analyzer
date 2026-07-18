import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  fetchAnomalyAnalysis,
  fetchCompanyProfile,
  fetchCompanySearch,
  fetchIndustryComparison,
  fetchIndustryCompanyComparison,
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

const industryComparisonYears = {
  defense: [2025, 2024, 2023, 2022, 2021],
  semiconductor: [2025, 2024, 2023],
  construction: [2025, 2024, 2023],
};

const industryOptions = [
  { id: "defense", label: "방산" },
  { id: "semiconductor", label: "반도체" },
  { id: "construction", label: "건설" },
];

const commonMetricDefinitions = [
  { code: "revenue", label: "매출액", unit: "KRW" },
  { code: "operating_margin", label: "영업이익률", unit: "%" },
  { code: "gross_margin", label: "매출총이익률", unit: "%" },
  { code: "net_margin", label: "순이익률", unit: "%" },
  { code: "debt_ratio", label: "부채비율", unit: "%" },
  { code: "current_ratio", label: "유동비율", unit: "%" },
  { code: "asset_turnover", label: "총자산회전율", unit: "배" },
  { code: "roe", label: "ROE", unit: "%" },
  { code: "cfo_conversion", label: "영업현금흐름 전환율", unit: "배" },
];

const inspectorAccountsByIndustry = {
  defense: ["매출액", "계약자산", "계약부채", "매출채권", "영업활동현금흐름"],
  semiconductor: ["매출액", "재고자산", "유형자산의 취득", "영업활동현금흐름"],
  construction: ["매출액", "계약자산(미청구공사)", "매출채권", "영업활동현금흐름"],
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

// Ratios/rates (%, 배) are signed and the sign is meaningful (loss vs profit,
// contraction vs growth); absolute KRW amounts are not colored by sign.
function signClass(value, unit) {
  if (value == null || Number.isNaN(value) || unit === "KRW") {
    return "";
  }
  if (value > 0) return "value-positive";
  if (value < 0) return "value-negative";
  return "";
}

function MiniSparkline({ values }) {
  const valid = values.map(Number).filter(Number.isFinite);
  if (valid.length < 2) return <span className="spark-empty">데이터 부족</span>;
  const min = Math.min(...valid);
  const range = Math.max(...valid) - min || Math.abs(Math.max(...valid)) || 1;
  const points = values.map((value, index) => {
    const numeric = Number(value);
    const x = 8 + (index * 92) / Math.max(values.length - 1, 1);
    const y = Number.isFinite(numeric) ? 40 - ((numeric - min) / range) * 28 : 40;
    return `${x},${y}`;
  });
  const last = points.at(-1).split(",");
  return <svg className={`mini-spark ${valid.at(-1) >= valid[0] ? "rising" : "falling"}`} viewBox="0 0 108 48" role="img" aria-label="5개년 추이"><polyline points={points.join(" ")} /><circle cx={last[0]} cy={last[1]} r="2.7" /></svg>;
}

function ComparisonKpiStrip({ comparison, rows }) {
  const scopedRows = rows || comparison.rows;
  const marginDefinition = comparison.metricDefinitions.find((definition) => definition.code === "operating_margin");
  const margins = scopedRows.map((row) => row.metrics.operating_margin).filter((value) => value != null).sort((left, right) => left - right);
  const medianMargin = margins.length ? margins[Math.floor(margins.length / 2)] : null;
  const signalCount = scopedRows.filter((row) => row.riskSignals.length > 0).length;
  const fullCoverage = scopedRows.filter((row) => row.completeness === row.requiredAccountCount).length;
  const tiles = [
    ["분석 대상", `${scopedRows.length}개사`, "선택 산업·연도·필터 기준"],
    ["검토 신호", `${signalCount}개사`, "하나 이상 신호 보유"],
    ["영업이익률 중앙값", formatComparisonValue(medianMargin, marginDefinition || { unit: "%" }), "값 보유 기업 기준"],
    ["필수 계정 충족", `${fullCoverage}/${scopedRows.length}`, "전체 필수 계정 보유"],
  ];
  return <div className="comparison-kpis">{tiles.map(([label, value, note]) => <article key={label}><span>{label}</span><strong>{value}</strong><em>{note}</em></article>)}</div>;
}

function ComparisonInspector({ comparison, detailData, isLoading, onOpenCompany, selectedRow }) {
  if (!selectedRow) return <aside className="comparison-inspector empty">왼쪽 표에서 기업을 선택하면 상세 분석이 표시됩니다.</aside>;
  const accounts = inspectorAccountsByIndustry[comparison.industryId] || inspectorAccountsByIndustry.semiconductor;
  const series = detailData?.accountSeries || [];
  return <aside className="comparison-inspector"><div className="inspector-head"><div><p className="eyebrow">선택 기업 분석</p><h3>{selectedRow.corpName}</h3><span>{selectedRow.stockCode} · {selectedRow.basis || "기준 미확인"} · 계정 {selectedRow.completeness}/{selectedRow.requiredAccountCount}</span></div><button className="text-button" onClick={() => onOpenCompany(selectedRow)} type="button">전체 분석 열기</button></div>{isLoading ? <div className="inspector-loading">기업 상세를 불러오는 중입니다.</div> : <><div className="inspector-sparks">{accounts.map((account) => { const values = series.map((point) => point.values[account]); return <article key={account}><div><span>{account}</span><strong>{formatCompactNumber(values.at(-1))}</strong></div><MiniSparkline values={values} /></article>; })}</div><div className="inspector-metrics">{comparison.metricDefinitions.map((definition) => <div key={definition.code}><span>{definition.label}</span><strong className={signClass(selectedRow.metrics[definition.code], definition.unit)}>{formatComparisonValue(selectedRow.metrics[definition.code], definition)}</strong></div>)}</div>{selectedRow.riskSignals.length ? <section className="inspector-signals">{selectedRow.riskSignals.map((signal) => <article key={signal.code}><div><strong>{signal.label}</strong><em>{signal.severity}</em></div><p>{signal.summary}</p></article>)}</section> : <p className="comparison-empty">현재 규칙의 검토 신호는 없습니다. 정상 또는 안전을 단정하지 않으며, 상세 계정과 사업 맥락을 함께 확인해야 합니다.</p>}{detailData?.auditQuestions?.length ? <section className="inspector-questions"><p className="eyebrow">감사 확인 질문</p>{detailData.auditQuestions.map((question) => <p key={question}>{question}</p>)}<em>{detailData.limitations}</em></section> : null}</>}</aside>;
}

function ComparisonControls({ activeIndustryId, onIndustryChange, year, availableYears, onYearChange, searchTerm, onSearchChange, riskFilter, onRiskFilterChange, riskLevels }) {
  return (
    <div className="comparison-controls">
      <div className="control-field">
        <span>산업</span>
        <div className="industry-tab-group" role="tablist">
          {industryOptions.map((option) => (
            <button
              aria-selected={activeIndustryId === option.id}
              className={`industry-tab ${activeIndustryId === option.id ? "active" : ""}`}
              key={option.id}
              onClick={() => onIndustryChange(option.id)}
              role="tab"
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <label className="control-field">
        <span>연도</span>
        <select disabled={!availableYears?.length} onChange={(event) => onYearChange(Number(event.target.value))} value={year}>
          {(availableYears?.length ? availableYears : [year]).map((option) => (
            <option key={option} value={option}>{option}년</option>
          ))}
        </select>
      </label>
      <label className="control-field search">
        <span>기업 검색</span>
        <input
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="기업명 또는 종목코드"
          type="text"
          value={searchTerm}
        />
      </label>
      <label className="control-field">
        <span>검토 신호</span>
        <select onChange={(event) => onRiskFilterChange(event.target.value)} value={riskFilter}>
          <option value="all">전체</option>
          {riskLevels.map((level) => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
      </label>
    </div>
  );
}

function IndustryComparisonTable({ comparison, activeIndustryId, onIndustryChange, year, availableYears, onYearChange, onOpenCompany }) {
  const [sortCode, setSortCode] = useState("revenue");
  const [sortDirection, setSortDirection] = useState("desc");
  const [searchTerm, setSearchTerm] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [selectedRow, setSelectedRow] = useState(() => comparison.rows[0] || null);
  const [detailData, setDetailData] = useState(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const definitions = commonMetricDefinitions;
  const riskLevels = useMemo(
    () => [...new Set(comparison.rows.map((row) => row.riskLevel))],
    [comparison.rows],
  );
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredRows = comparison.rows.filter((row) => {
    const matchesSearch = !normalizedSearch
      || row.corpName.toLowerCase().includes(normalizedSearch)
      || (row.stockCode || "").toLowerCase().includes(normalizedSearch);
    const matchesRisk = riskFilter === "all" || row.riskLevel === riskFilter;
    return matchesSearch && matchesRisk;
  });
  const sortedRows = [...filteredRows].sort((left, right) => ((sortDirection === "desc" ? 1 : -1) * ((right.metrics[sortCode] ?? Number.NEGATIVE_INFINITY) - (left.metrics[sortCode] ?? Number.NEGATIVE_INFINITY))));

  useEffect(() => {
    setSelectedRow(filteredRows[0] || null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comparison.industryId, comparison.year, searchTerm, riskFilter]);

  useEffect(() => {
    if (!selectedRow) return undefined;
    let cancelled = false;
    setIsDetailLoading(true);
    setDetailData(null);
    fetchIndustryCompanyComparison(comparison.industryId, selectedRow.corpCode, comparison.year).then((data) => { if (!cancelled) setDetailData(data); }).catch(() => { if (!cancelled) setDetailData(null); }).finally(() => { if (!cancelled) setIsDetailLoading(false); });
    return () => { cancelled = true; };
  }, [comparison.industryId, comparison.year, selectedRow?.corpCode]);

  function selectSort(code) { if (code === sortCode) setSortDirection((current) => current === "desc" ? "asc" : "desc"); else { setSortCode(code); setSortDirection("desc"); } }

  return <section className="comparison-section"><div className="comparison-head"><div><p className="eyebrow">전체 기업 · {comparison.year}</p><h2>{industryLabels[comparison.industryId] || comparison.industryId} 기업 목록</h2><p>{comparison.industryId === "construction" ? "A/B/C 분류 전 전체 표본을 보는 탐색용 비교입니다. 신호는 검토 우선순위이며, 정식 동종 벤치마크는 아닙니다." : "연결(CFS) 우선으로 수집하며, 값이 없을 경우 별도(OFS) 기준을 사용합니다."}</p></div></div><ComparisonControls activeIndustryId={activeIndustryId} availableYears={availableYears} onIndustryChange={onIndustryChange} onRiskFilterChange={setRiskFilter} onSearchChange={setSearchTerm} onYearChange={onYearChange} riskFilter={riskFilter} riskLevels={riskLevels} searchTerm={searchTerm} year={year} /><ComparisonKpiStrip comparison={comparison} rows={filteredRows} /><div className="comparison-workbench"><div className="comparison-table-wrap">{sortedRows.length ? <table className="comparison-table"><thead><tr><th>기업</th><th>기준</th><th>데이터</th>{comparison.industryId === "construction" ? <th>비교군 후보</th> : null}<th>검토 신호</th>{definitions.map((definition) => <th key={definition.code}><button onClick={() => selectSort(definition.code)} type="button">{definition.label} {sortCode === definition.code ? (sortDirection === "desc" ? "↓" : "↑") : "↕"}</button></th>)}</tr></thead><tbody>{sortedRows.map((row) => <tr className={selectedRow?.corpCode === row.corpCode ? "selected" : ""} key={row.corpCode} onClick={() => setSelectedRow(row)}><td><strong>{row.corpName}</strong><span>{row.stockCode}</span></td><td>{row.basis || "N/A"}</td><td>{row.completeness}/{row.requiredAccountCount}</td>{comparison.industryId === "construction" ? <td>{row.peerGroupSuggestion || "검토 필요"}</td> : null}<td><em className={`risk-badge ${row.riskLevel}`}>{row.riskLevel}</em></td>{definitions.map((definition) => <td className={signClass(row.metrics[definition.code], definition.unit)} key={definition.code}>{formatComparisonValue(row.metrics[definition.code], definition)}</td>)}</tr>)}</tbody></table> : <p className="comparison-empty">조건에 맞는 기업이 없습니다. 검색어나 신호 필터를 조정하세요.</p>}</div><ComparisonInspector comparison={comparison} detailData={detailData} isLoading={isDetailLoading} onOpenCompany={onOpenCompany} selectedRow={selectedRow} /></div></section>;
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
              <strong className={signClass(metricData.currentValue, "%")}>{metricData.currentDisplay}</strong>
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

function SemiconductorPanel({ data, industryId = "semiconductor", isLoading }) {
  const isConstruction = industryId === "construction";
  const industryLabel = industryLabels[industryId] || industryId;
  if (isLoading) return <div className="loading-panel">{industryLabel} 위험 신호를 불러오는 중입니다.</div>;
  if (!data) return null;
  const accounts = isConstruction ? ["매출액", "계약자산(미청구공사)", "매출채권", "차입금", "충당부채", "영업활동현금흐름"] : ["매출액", "재고자산", "유형자산의 취득", "영업활동현금흐름"];
  return <div className="analysis-panel"><div className="panel-toolbar"><div><p className="eyebrow">{industryLabel} 리스크 개요</p><h4>{data.row.riskLevel} · 2025년</h4></div><span>{data.row.basis || "기준 없음"} · 계정 {data.row.completeness}/{data.row.requiredAccountCount}</span></div><div className="indicator-grid">{data.metricDefinitions.map((definition) => <article className="indicator-card" key={definition.code}><span>{definition.label}</span><strong className={signClass(data.row.metrics[definition.code], definition.unit)}>{formatComparisonValue(data.row.metrics[definition.code], definition)}</strong><em>{isConstruction ? "전체 표본 초기 기준" : "산업 비교 기준"}</em></article>)}</div><div className="signal-stack">{data.row.riskSignals.length ? data.row.riskSignals.map((signal) => <article className="signal-card triggered" key={signal.code}><div className="signal-head"><strong>{signal.label}</strong><span>{signal.severity}</span></div><p>{signal.summary}</p></article>) : <div className="status-banner warning">현재 규칙의 검토 신호는 없습니다. 상세 계정과 사업 맥락을 함께 확인하세요.</div>}</div><section className="account-series"><div><p className="eyebrow">원천 계정 5개년</p><h5>{isConstruction ? "계약자산·채권·차입금·현금흐름의 방향을 확인하세요." : "재고·투자·현금흐름의 방향을 확인하세요."}</h5></div><div className="account-series-table"><div className="series-head"><span>계정</span>{data.accountSeries.map((point) => <span key={point.year}>{point.year} · {point.basis || "N/A"}</span>)}</div>{accounts.map((account) => <div className="series-line" key={account}><strong>{account}</strong>{data.accountSeries.map((point) => <span key={point.year}>{formatCompactNumber(point.values[account])}</span>)}</div>)}</div></section><section className="audit-questions"><p className="eyebrow">근거 메타데이터와 감사 확인 질문</p><p className="source-status">현재 재무 계정·비교 산식은 연결되어 있습니다. 원문 DART 공시 링크는 접수번호 데이터가 적재되면 연결됩니다.</p>{data.auditQuestions.map((question) => <p key={question}>{question}</p>)}<em>{data.limitations}</em></section></div>;
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
  semiconductorData,
  isSemiconductorLoading,
  constructionData,
  isConstructionLoading,
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

      {isDefenseWorkspace || ["semiconductor", "construction"].includes(selectedIndustryId) ? (
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

        {selectedIndustryId === "semiconductor" ? <SemiconductorPanel data={semiconductorData} isLoading={isSemiconductorLoading} /> : null}
        {selectedIndustryId === "construction" ? <SemiconductorPanel data={constructionData} industryId="construction" isLoading={isConstructionLoading} /> : null}
        {!isDefenseWorkspace && !["semiconductor", "construction"].includes(selectedIndustryId) ? (
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
  const [semiconductorData, setSemiconductorData] = useState(null);
  const [isSemiconductorLoading, setIsSemiconductorLoading] = useState(false);
  const [constructionData, setConstructionData] = useState(null);
  const [isConstructionLoading, setIsConstructionLoading] = useState(false);
  const [tableIndustryId, setTableIndustryId] = useState("defense");
  const [tableYear, setTableYear] = useState(2025);
  const [tableComparison, setTableComparison] = useState(null);
  const [isTableLoading, setIsTableLoading] = useState(false);
  const [tableError, setTableError] = useState("");

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
    setSemiconductorData(null);
    setConstructionData(null);
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
    let cancelled = false;
    setIsTableLoading(true);
    setTableError("");
    fetchIndustryComparison(tableIndustryId, tableYear)
      .then((data) => {
        if (!cancelled) {
          setTableComparison(data);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setTableComparison(null);
          setTableError(caught instanceof Error ? caught.message : "전체 기업 목록을 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsTableLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tableIndustryId, tableYear]);

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

  useEffect(() => {
    if (!profile || selectedIndustryId !== "semiconductor") return;
    let cancelled = false;
    setIsSemiconductorLoading(true);
    fetchIndustryCompanyComparison("semiconductor", profile.company.corp_code).then((data) => { if (!cancelled) setSemiconductorData(data); }).catch((caught) => { if (!cancelled) setError(caught instanceof Error ? caught.message : "반도체 분석을 불러오지 못했습니다."); }).finally(() => { if (!cancelled) setIsSemiconductorLoading(false); });
    return () => { cancelled = true; };
  }, [profile, selectedIndustryId]);

  useEffect(() => {
    if (!profile || selectedIndustryId !== "construction") return;
    let cancelled = false;
    setIsConstructionLoading(true);
    fetchIndustryCompanyComparison("construction", profile.company.corp_code).then((data) => { if (!cancelled) setConstructionData(data); }).catch((caught) => { if (!cancelled) setError(caught instanceof Error ? caught.message : "건설 분석을 불러오지 못했습니다."); }).finally(() => { if (!cancelled) setIsConstructionLoading(false); });
    return () => { cancelled = true; };
  }, [profile, selectedIndustryId]);

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
    setSemiconductorData(null);
    setConstructionData(null);
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
            <button className="search-button" disabled={isResolving} type="submit">
              {isResolving ? "검색 중" : "검색"}
            </button>
          </form>
        </header>

        <main className="content-stage">
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
              semiconductorData={semiconductorData}
              constructionData={constructionData}
              showDetails={showDetails}
              isSemiconductorLoading={isSemiconductorLoading}
              isConstructionLoading={isConstructionLoading}
            />
          ) : isTableLoading ? (
            <div className="loading-panel">전체 기업 목록을 불러오는 중입니다.</div>
          ) : tableError ? (
            <div className="status-banner error">{tableError}</div>
          ) : tableComparison ? (
            <IndustryComparisonTable
              activeIndustryId={tableIndustryId}
              availableYears={industryComparisonYears[tableIndustryId] || []}
              comparison={tableComparison}
              onIndustryChange={setTableIndustryId}
              onOpenCompany={(row) => openCompanyProfileFromSuggestion({ companyId: row.corpCode, companyName: row.corpName })}
              onYearChange={setTableYear}
              year={tableYear}
            />
          ) : null}
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
