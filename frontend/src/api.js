const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function parseResponse(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.message || "분석 중 오류가 발생했습니다.");
  }

  return response.json();
}

export async function fetchDebtRatio(query) {
  let response;
  try {
    response = await fetch(`${baseUrl}/api/debt-ratio?query=${encodeURIComponent(query)}`);
  } catch {
    throw new Error("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return parseResponse(response);
}

export async function fetchAnalyses() {
  let response;
  try {
    response = await fetch(`${baseUrl}/api/analyses`);
  } catch {
    throw new Error("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return parseResponse(response);
}

export async function fetchCompanySearch(query) {
  let response;
  try {
    response = await fetch(`${baseUrl}/api/company-search?q=${encodeURIComponent(query)}`);
  } catch {
    throw new Error("검색 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return parseResponse(response);
}

export async function fetchCompanyOverview(companyId) {
  let response;
  try {
    response = await fetch(`${baseUrl}/api/company-overview?company_id=${encodeURIComponent(companyId)}`);
  } catch {
    throw new Error("개요 데이터를 불러오지 못했습니다.");
  }

  return parseResponse(response);
}

export async function runAnalysis(query, analysisCode) {
  let response;
  try {
    response = await fetch(
      `${baseUrl}/api/analyze?query=${encodeURIComponent(query)}&analysis_code=${encodeURIComponent(analysisCode)}`,
    );
  } catch {
    throw new Error("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return parseResponse(response);
}

export async function runAnalyses(query, analysisCodes) {
  let response;
  const joinedCodes = analysisCodes.join(",");

  try {
    response = await fetch(
      `${baseUrl}/api/analyze-many?query=${encodeURIComponent(query)}&analysis_codes=${encodeURIComponent(joinedCodes)}`,
    );
  } catch {
    throw new Error("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return parseResponse(response);
}
