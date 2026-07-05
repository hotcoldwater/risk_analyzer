import { dartFetch } from "./client";
import type { CompanyProfile, DartCompanyResponse } from "../../types/dart";

export async function fetchCompanyProfile(
  corpCode: string,
  apiKey: string | undefined
): Promise<CompanyProfile> {
  const data = await dartFetch<DartCompanyResponse>("company.json", {
    corp_code: corpCode
  }, apiKey);

  return {
    corpCode: data.corp_code ?? corpCode,
    corpName: data.corp_name ?? "",
    stockCode: data.stock_code || undefined,
    corpClass: data.corp_cls || undefined,
    industryCode: data.induty_code || undefined,
    fiscalMonth: data.acc_mt || undefined
  };
}
