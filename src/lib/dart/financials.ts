import { dartFetch } from "./client";
import type { DartFinancialStatementResponse } from "../../types/dart";
import type { FsDiv, ReportCode } from "../../types/financial";

export async function fetchFinancialStatement(params: {
  corpCode: string;
  year: string;
  reportCode: ReportCode;
  fsDiv: FsDiv;
}, apiKey: string | undefined): Promise<DartFinancialStatementResponse> {
  return dartFetch<DartFinancialStatementResponse>("fnlttSinglAcntAll.json", {
    corp_code: params.corpCode,
    bsns_year: params.year,
    reprt_code: params.reportCode,
    fs_div: params.fsDiv
  }, apiKey);
}

export async function fetchFinancialStatementsForPeriod(params: {
  corpCode: string;
  startYear: number;
  endYear: number;
  reportCode: ReportCode;
  fsDiv: FsDiv;
}, apiKey: string | undefined): Promise<
  Array<{
    year: number;
    response: DartFinancialStatementResponse | null;
    fsDivUsed: FsDiv;
    fallbackApplied: boolean;
    error?: string;
  }>
> {
  const years = Array.from(
    { length: params.endYear - params.startYear + 1 },
    (_, index) => params.startYear + index
  );

  return Promise.all(
    years.map(async (year) => {
      try {
        const response = await fetchFinancialStatement({
          corpCode: params.corpCode,
          year: String(year),
          reportCode: params.reportCode,
          fsDiv: params.fsDiv
        }, apiKey);

        return {
          year,
          response,
          fsDivUsed: params.fsDiv,
          fallbackApplied: false
        };
      } catch (error) {
        if (params.fsDiv === "CFS") {
          try {
            const fallback = await fetchFinancialStatement({
              corpCode: params.corpCode,
              year: String(year),
              reportCode: params.reportCode,
              fsDiv: "OFS"
            }, apiKey);

            return {
              year,
              response: fallback,
              fsDivUsed: "OFS" as const,
              fallbackApplied: true
            };
          } catch (fallbackError) {
            return {
              year,
              response: null,
              fsDivUsed: params.fsDiv,
              fallbackApplied: false,
              error: fallbackError instanceof Error ? fallbackError.message : String(fallbackError)
            };
          }
        }

        return {
          year,
          response: null,
          fsDivUsed: params.fsDiv,
          fallbackApplied: false,
          error: error instanceof Error ? error.message : String(error)
        };
      }
    })
  );
}
