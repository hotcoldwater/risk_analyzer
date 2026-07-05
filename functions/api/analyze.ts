import type { PagesContext, PagesEnv } from "../_shared";
import { fail, ok } from "../_shared";
import { analyzeCashFlowGap } from "../../src/lib/analysis/cashFlowGap";
import { calculateDebtRatio } from "../../src/lib/analysis/debtRatio";
import { detectAccountSurges } from "../../src/lib/analysis/detectSurge";
import { normalizeFinancialStatement } from "../../src/lib/analysis/normalize";
import { fetchCompanyProfile } from "../../src/lib/dart/company";
import { fetchFinancialStatementsForPeriod } from "../../src/lib/dart/financials";
import { createApiError } from "../../src/lib/utils/errors";
import type { FsDiv, ReportCode } from "../../src/types/financial";

type AnalyzeRequestBody = {
  corpCode?: string;
  corpName?: string;
  startYear?: number;
  endYear?: number;
  reportCode?: ReportCode;
  fsDiv?: FsDiv;
};

function buildSummary(financials: Array<{ year: number; debtRatioPercent: number | null }>) {
  const valid = financials.filter((item) => item.debtRatioPercent !== null);

  if (valid.length < 2) {
    return "분석기간 동안 부채비율 추이를 계산했습니다. 일부 연도는 데이터가 부족해 추가 검토가 필요합니다.";
  }

  const first = valid[0];
  const last = valid[valid.length - 1];
  const direction =
    (last.debtRatioPercent ?? 0) >= (first.debtRatioPercent ?? 0) ? "상승" : "하락";

  return `분석기간 동안 부채비율은 ${first.year}년 ${first.debtRatioPercent?.toFixed(1)}%에서 ${last.year}년 ${last.debtRatioPercent?.toFixed(1)}%로 ${direction}했습니다. 재무구조 변화에 대한 추가 검토가 필요할 수 있습니다.`;
}

export async function onRequestPost(context: PagesContext<PagesEnv>) {
  try {
    const body = (await context.request.json()) as AnalyzeRequestBody;

    if (!body.corpCode || !body.startYear || !body.endYear || !body.reportCode || !body.fsDiv) {
      throw createApiError("분석 요청 값이 올바르지 않습니다.", "INVALID_ANALYZE_REQUEST", 400);
    }

    if (body.startYear > body.endYear) {
      throw createApiError("시작연도는 종료연도보다 클 수 없습니다.", "INVALID_YEAR_RANGE", 400);
    }

    const company = await fetchCompanyProfile(body.corpCode, context.env.DART_API_KEY);
    const yearlyFinancials = await fetchFinancialStatementsForPeriod(
      {
        corpCode: body.corpCode,
        startYear: body.startYear,
        endYear: body.endYear,
        reportCode: body.reportCode,
        fsDiv: body.fsDiv
      },
      context.env.DART_API_KEY
    );

    const normalized = yearlyFinancials
      .filter((item) => item.response?.list?.length)
      .map((item) =>
        normalizeFinancialStatement({
          year: item.year,
          fsDiv: item.fsDivUsed,
          reportCode: body.reportCode as ReportCode,
          items: item.response?.list ?? []
        })
      );

    if (normalized.length === 0) {
      throw createApiError(
        "해당 기간의 재무제표 데이터를 찾을 수 없습니다.",
        "NO_FINANCIAL_DATA",
        404
      );
    }

    const financials = calculateDebtRatio(normalized);
    const riskSignals = [...detectAccountSurges(normalized), ...analyzeCashFlowGap(normalized)];

    return ok({
      company,
      period: {
        startYear: body.startYear,
        endYear: body.endYear,
        reportCode: body.reportCode,
        fsDiv: body.fsDiv
      },
      financials,
      yearlyStatus: yearlyFinancials.map((item) => ({
        year: item.year,
        fetched: Boolean(item.response?.list?.length),
        fsDivUsed: item.fsDivUsed,
        fallbackApplied: item.fallbackApplied,
        error: item.error ?? null
      })),
      riskSignals,
      summary: buildSummary(financials)
    });
  } catch (error) {
    return fail(error);
  }
}
