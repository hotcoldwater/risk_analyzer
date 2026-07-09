const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function parseResponse(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.message || "요청을 처리하지 못했습니다.");
  }

  return response.json();
}

async function fetchJson(path, fallbackMessage) {
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`);
  } catch {
    throw new Error(fallbackMessage);
  }
  return parseResponse(response);
}

export function fetchCompanySearch(query) {
  return fetchJson(
    `/api/company-search?q=${encodeURIComponent(query)}`,
    "검색 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
  );
}

export function fetchResolvedCompany(query) {
  return fetchJson(
    `/api/company-resolve?query=${encodeURIComponent(query)}`,
    "기업 정보를 불러오지 못했습니다.",
  );
}

export function fetchCompanyProfile(corpCode) {
  return fetchJson(
    `/api/company-profile?corp_code=${encodeURIComponent(corpCode)}`,
    "기업 정보를 불러오지 못했습니다.",
  );
}

export function fetchLiquidityMetric(corpCode, metricCode, groupScope) {
  return fetchJson(
    `/api/analysis/liquidity-metric?corp_code=${encodeURIComponent(corpCode)}&metric_code=${encodeURIComponent(metricCode)}&group_scope=${encodeURIComponent(groupScope)}`,
    "현금화 리스크 분석을 불러오지 못했습니다.",
  );
}

export function fetchAnomalyAnalysis(corpCode, groupScope) {
  return fetchJson(
    `/api/analysis/anomaly?corp_code=${encodeURIComponent(corpCode)}&group_scope=${encodeURIComponent(groupScope)}`,
    "이상징후 분석을 불러오지 못했습니다.",
  );
}
