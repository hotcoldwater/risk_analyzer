const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export async function fetchDebtRatio(query) {
  let response;
  try {
    response = await fetch(`${baseUrl}/api/debt-ratio?query=${encodeURIComponent(query)}`);
  } catch {
    throw new Error("분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.message || "분석 중 오류가 발생했습니다.");
  }

  return response.json();
}
