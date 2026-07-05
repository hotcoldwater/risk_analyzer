import "../styles/site.css";
import { formatKoreanCurrency, formatPercent } from "../lib/utils/format";
import type { RiskSignal } from "../types/analysis";
import type { CompanyProfile, CorpSummary } from "../types/dart";
import type { DebtRatioResult, FsDiv, ReportCode } from "../types/financial";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

type ApiSuccess<T> = {
  success: true;
  data: T;
};

type ApiFailure = {
  success: false;
  error: string;
  detail?: string;
};

type SearchResponse = ApiSuccess<CorpSummary[]> | ApiFailure;

type AnalyzeData = {
  company: CompanyProfile;
  period: {
    startYear: number;
    endYear: number;
    reportCode: ReportCode;
    fsDiv: FsDiv;
  };
  financials: DebtRatioResult[];
  yearlyStatus: Array<{
    year: number;
    fetched: boolean;
    fsDivUsed: FsDiv;
    fallbackApplied: boolean;
    error: string | null;
  }>;
  riskSignals: RiskSignal[];
  summary: string;
};

type AnalyzeResponse = ApiSuccess<AnalyzeData> | ApiFailure;

const currentYear = new Date().getFullYear();

type State = {
  searchResults: CorpSummary[];
  selectedCompany: CorpSummary | null;
  result: AnalyzeData | null;
  error: string | null;
  searching: boolean;
  analyzing: boolean;
};

const state: State = {
  searchResults: [],
  selectedCompany: null,
  result: null,
  error: null,
  searching: false,
  analyzing: false
};

const yearOptions = Array.from({ length: 10 }, (_, index) => currentYear - index);

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("앱 루트를 찾을 수 없습니다.");
}

app.innerHTML = `
  <main class="page-shell">
    <section class="hero-card">
      <p class="eyebrow">Audit-focused MVP</p>
      <h1>DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스</h1>
      <p class="hero-copy">기업 검색, 실제 DART 재무제표 조회, 부채비율 계산, 기본 위험 신호 분석까지 한 화면에서 확인합니다.</p>
    </section>

    <section class="panel">
      <div class="form-grid">
        <label class="field field-span">
          <span>기업명 검색</span>
          <div class="search-row">
            <input id="query" placeholder="예: 삼성전자" />
            <button id="search-button" class="button button-dark">검색</button>
          </div>
        </label>
        <label class="field">
          <span>시작연도</span>
          <select id="startYear"></select>
        </label>
        <label class="field">
          <span>종료연도</span>
          <select id="endYear"></select>
        </label>
        <label class="field">
          <span>보고서 유형</span>
          <select id="reportCode">
            <option value="11011">사업보고서</option>
            <option value="11012">반기보고서</option>
            <option value="11013">1분기보고서</option>
            <option value="11014">3분기보고서</option>
          </select>
        </label>
        <label class="field">
          <span>재무제표 구분</span>
          <select id="fsDiv">
            <option value="CFS">연결재무제표</option>
            <option value="OFS">별도재무제표</option>
          </select>
        </label>
      </div>
      <div id="search-error" class="inline-error" hidden></div>
      <div id="search-results" class="search-results"></div>
      <button id="analyze-button" class="button button-accent" disabled>분석 실행</button>
    </section>

    <section id="result-area" class="result-stack">
      <article class="panel empty-state">
        <h2>안내</h2>
        <p>기업 검색 후 분석 조건을 선택하면 연도별 부채총계, 자본총계, 부채비율과 기본 위험 신호를 확인할 수 있습니다.</p>
      </article>
    </section>
  </main>
`;

const queryInput = document.querySelector<HTMLInputElement>("#query")!;
const searchButton = document.querySelector<HTMLButtonElement>("#search-button")!;
const analyzeButton = document.querySelector<HTMLButtonElement>("#analyze-button")!;
const startYearSelect = document.querySelector<HTMLSelectElement>("#startYear")!;
const endYearSelect = document.querySelector<HTMLSelectElement>("#endYear")!;
const reportCodeSelect = document.querySelector<HTMLSelectElement>("#reportCode")!;
const fsDivSelect = document.querySelector<HTMLSelectElement>("#fsDiv")!;
const searchResultsNode = document.querySelector<HTMLDivElement>("#search-results")!;
const searchErrorNode = document.querySelector<HTMLDivElement>("#search-error")!;
const resultArea = document.querySelector<HTMLElement>("#result-area")!;

function apiUrl(path: string) {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

yearOptions.forEach((year, index) => {
  startYearSelect.insertAdjacentHTML(
    "beforeend",
    `<option value="${year}" ${index === 4 ? "selected" : ""}>${year}</option>`
  );
  endYearSelect.insertAdjacentHTML(
    "beforeend",
    `<option value="${year}" ${index === 0 ? "selected" : ""}>${year}</option>`
  );
});

searchButton.addEventListener("click", handleSearch);
analyzeButton.addEventListener("click", handleAnalyze);

function setError(message: string | null) {
  state.error = message;
  if (!message) {
    searchErrorNode.hidden = true;
    searchErrorNode.textContent = "";
    return;
  }

  searchErrorNode.hidden = false;
  searchErrorNode.textContent = message;
}

function renderSearchResults() {
  if (state.searchResults.length === 0) {
    searchResultsNode.innerHTML = "";
    return;
  }

  searchResultsNode.innerHTML = `
    <div class="result-list">
      ${state.searchResults
        .map((company) => {
          const active = state.selectedCompany?.corpCode === company.corpCode;
          return `
            <button class="company-item ${active ? "is-active" : ""}" data-corp="${company.corpCode}">
              <strong>${company.corpName}</strong>
              <span>종목코드 ${company.stockCode || "N/A"} / DART ${company.corpCode}</span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;

  searchResultsNode.querySelectorAll<HTMLButtonElement>("[data-corp]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCompany =
        state.searchResults.find((company) => company.corpCode === button.dataset.corp) ?? null;
      analyzeButton.disabled = !state.selectedCompany || state.analyzing;
      renderSearchResults();
    });
  });
}

function buildChart(financials: DebtRatioResult[]) {
  const valid = financials.filter((item) => item.debtRatioPercent !== null);
  if (valid.length === 0) {
    return `<p class="muted">그래프를 그릴 데이터가 부족합니다.</p>`;
  }

  const max = Math.max(...valid.map((item) => item.debtRatioPercent ?? 0), 1);
  const points = valid
    .map((item, index) => {
      const x = valid.length === 1 ? 200 : (index / (valid.length - 1)) * 360 + 20;
      const y = 180 - ((item.debtRatioPercent ?? 0) / max) * 140;
      return { x, y, year: item.year, label: formatPercent(item.debtRatioPercent) };
    });

  return `
    <svg viewBox="0 0 400 220" class="chart">
      <line x1="20" y1="180" x2="380" y2="180" stroke="#c6d8e6" />
      <line x1="20" y1="20" x2="20" y2="180" stroke="#c6d8e6" />
      <polyline fill="none" stroke="#0f6c86" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"
        points="${points.map((point) => `${point.x},${point.y}`).join(" ")}" />
      ${points
        .map(
          (point) => `
            <circle cx="${point.x}" cy="${point.y}" r="5" fill="#0f6c86" />
            <text x="${point.x}" y="${point.y - 12}" text-anchor="middle" font-size="11" fill="#102033">${point.label}</text>
            <text x="${point.x}" y="202" text-anchor="middle" font-size="12" fill="#556575">${point.year}</text>
          `
        )
        .join("")}
    </svg>
  `;
}

function renderResult() {
  if (state.error) {
    resultArea.innerHTML = `<article class="panel error-panel">${state.error}</article>`;
    return;
  }

  if (!state.result) {
    resultArea.innerHTML = `
      <article class="panel empty-state">
        <h2>안내</h2>
        <p>기업 검색 후 분석 조건을 선택하면 연도별 부채총계, 자본총계, 부채비율과 기본 위험 신호를 확인할 수 있습니다.</p>
      </article>
    `;
    return;
  }

  const { company, period, financials, riskSignals, summary, yearlyStatus } = state.result;

  resultArea.innerHTML = `
    <section class="card-grid">
      <article class="panel info-card">
        <h2>기업 기본정보</h2>
        <dl class="info-grid">
          <div><dt>기업명</dt><dd>${company.corpName}</dd></div>
          <div><dt>종목코드</dt><dd>${company.stockCode || "N/A"}</dd></div>
          <div><dt>DART 고유번호</dt><dd>${company.corpCode}</dd></div>
          <div><dt>업종코드</dt><dd>${company.industryCode || "N/A"}</dd></div>
        </dl>
      </article>
      <article class="panel info-card">
        <h2>분석 조건</h2>
        <dl class="info-grid">
          <div><dt>분석기간</dt><dd>${period.startYear} - ${period.endYear}</dd></div>
          <div><dt>보고서 코드</dt><dd>${period.reportCode}</dd></div>
          <div><dt>재무제표</dt><dd>${period.fsDiv}</dd></div>
          <div><dt>요약</dt><dd>${summary}</dd></div>
        </dl>
      </article>
    </section>

    <article class="panel">
      <h2>연도별 부채비율</h2>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>연도</th>
              <th>부채총계</th>
              <th>자본총계</th>
              <th>부채비율</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            ${financials
              .map(
                (item) => `
                  <tr>
                    <td>${item.year}</td>
                    <td>${formatKoreanCurrency(item.totalLiabilities)}</td>
                    <td>${formatKoreanCurrency(item.totalEquity)}</td>
                    <td>${formatPercent(item.debtRatioPercent)}</td>
                    <td>${item.status}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </article>

    <section class="card-grid">
      <article class="panel">
        <div class="section-head">
          <h2>부채비율 추이</h2>
          <span>단위: %</span>
        </div>
        ${buildChart(financials)}
      </article>
      <article class="panel">
        <h2>기본 위험 신호</h2>
        ${
          riskSignals.length === 0
            ? `<p class="muted">현재 규칙 기준으로 뚜렷한 이상징후는 감지되지 않았습니다. 다만 추가 검토가 필요할 수 있습니다.</p>`
            : `<div class="signal-list">${riskSignals
                .map(
                  (signal) => `
                    <article class="signal-card">
                      <div class="signal-head">
                        <strong>${signal.title}</strong>
                        <span>${signal.severity}</span>
                      </div>
                      <p>${signal.description}</p>
                    </article>
                  `
                )
                .join("")}</div>`
        }
      </article>
    </section>

    <article class="panel">
      <h2>연도별 조회 상태</h2>
      <div class="status-grid">
        ${yearlyStatus
          .map(
            (item) => `
              <article class="status-card">
                <strong>${item.year}년</strong>
                <p>조회 결과: ${item.fetched ? "성공" : "실패"}</p>
                <p>사용 재무제표: ${item.fsDivUsed}</p>
                <p>연결 fallback: ${item.fallbackApplied ? "적용" : "없음"}</p>
                ${item.error ? `<p class="status-error">${item.error}</p>` : ""}
              </article>
            `
          )
          .join("")}
      </div>
    </article>
  `;
}

async function handleSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setError("기업명을 입력해 주세요.");
    return;
  }

  state.searching = true;
  searchButton.disabled = true;
  searchButton.textContent = "검색 중";
  setError(null);
  state.selectedCompany = null;
  analyzeButton.disabled = true;

  try {
    const response = await fetch(apiUrl(`/search-company?query=${encodeURIComponent(query)}`));
    const payload = (await response.json()) as SearchResponse;

      if (!payload.success) {
        throw new Error(payload.error || payload.detail || "기업을 찾을 수 없습니다.");
      }

    state.searchResults = payload.data;
    if (payload.data.length === 0) {
      setError("기업을 찾을 수 없습니다.");
    }
  } catch (error) {
    state.searchResults = [];
    setError(error instanceof Error ? error.message : "기업 검색 중 오류가 발생했습니다.");
  } finally {
    state.searching = false;
    searchButton.disabled = false;
    searchButton.textContent = "검색";
    renderSearchResults();
  }
}

async function handleAnalyze() {
  if (!state.selectedCompany) {
    setError("검색 결과에서 기업을 선택해 주세요.");
    return;
  }

  state.analyzing = true;
  analyzeButton.disabled = true;
  analyzeButton.textContent = "분석 중";
  setError(null);
  renderResult();

  try {
    const response = await fetch(apiUrl("/analyze"), {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        corpCode: state.selectedCompany.corpCode,
        corpName: state.selectedCompany.corpName,
        startYear: Number(startYearSelect.value),
        endYear: Number(endYearSelect.value),
        reportCode: reportCodeSelect.value,
        fsDiv: fsDivSelect.value
      })
    });

    const payload = (await response.json()) as AnalyzeResponse;
      if (!payload.success) {
        throw new Error(payload.error || payload.detail || "분석 중 오류가 발생했습니다.");
      }

    state.result = payload.data;
  } catch (error) {
    state.result = null;
    setError(error instanceof Error ? error.message : "분석 중 오류가 발생했습니다.");
  } finally {
    state.analyzing = false;
    analyzeButton.disabled = !state.selectedCompany;
    analyzeButton.textContent = "분석 실행";
    renderResult();
  }
}

renderResult();
