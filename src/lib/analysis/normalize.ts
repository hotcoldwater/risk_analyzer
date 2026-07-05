import type { DartFinancialStatementItem } from "@/types/dart";
import type { NormalizedFinancialData, StandardAccountKey } from "@/types/financial";

const accountNameMap: Array<{
  key: StandardAccountKey;
  keywords: string[];
}> = [
  { keywords: ["매출액", "수익", "영업수익"], key: "revenue" },
  { keywords: ["영업이익", "영업손익"], key: "operatingProfit" },
  { keywords: ["당기순이익", "당기순손익"], key: "netIncome" },
  { keywords: ["영업활동현금흐름", "영업활동으로 인한 현금흐름"], key: "operatingCashFlow" },
  { keywords: ["매출채권 및 기타채권", "매출채권"], key: "accountsReceivable" },
  { keywords: ["재고자산"], key: "inventory" },
  { keywords: ["무형자산"], key: "intangibleAssets" },
  { keywords: ["자산총계"], key: "totalAssets" },
  { keywords: ["부채총계"], key: "totalLiabilities" },
  { keywords: ["자본총계"], key: "totalEquity" }
];

const statementPriority: Record<string, number> = {
  BS: 3,
  CIS: 2,
  IS: 2,
  CF: 1
};

function parseAmount(value?: string): number | undefined {
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  if (!trimmed || trimmed === "-") {
    return undefined;
  }

  const normalized = trimmed
    .replace(/,/g, "")
    .replace(/\s/g, "")
    .replace(/^\((.*)\)$/, "-$1");

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeName(name?: string) {
  return (name || "").replace(/\s+/g, "").toLowerCase();
}

function findStandardAccountKey(item: DartFinancialStatementItem): StandardAccountKey | undefined {
  const accountName = normalizeName(item.account_nm);
  const detailName = normalizeName(item.account_detail);

  for (const mapping of accountNameMap) {
    for (const keyword of mapping.keywords) {
      const target = normalizeName(keyword);
      if (accountName.includes(target) || detailName.includes(target)) {
        return mapping.key;
      }
    }
  }

  return undefined;
}

export function normalizeFinancialStatement(params: {
  year: number;
  fsDiv: "CFS" | "OFS";
  reportCode: "11011" | "11012" | "11013" | "11014";
  items: DartFinancialStatementItem[];
}): NormalizedFinancialData {
  const normalized: NormalizedFinancialData = {
    year: params.year,
    fsDiv: params.fsDiv,
    reportCode: params.reportCode,
    rawItems: params.items
  };

  const chosenScore = new Map<StandardAccountKey, number>();

  for (const item of params.items) {
    const key = findStandardAccountKey(item);
    if (!key) {
      continue;
    }

    const amount = parseAmount(item.thstrm_amount);
    if (amount === undefined) {
      continue;
    }

    const priority = statementPriority[item.sj_div ?? ""] ?? 0;
    const nameScore = normalizeName(item.account_nm) === normalizeName(accountNameMap.find((x) => x.key === key)?.keywords[0]) ? 2 : 1;
    const score = priority * 10 + nameScore;

    if ((chosenScore.get(key) ?? -1) >= score) {
      continue;
    }

    chosenScore.set(key, score);
    normalized[key] = amount;
  }

  return normalized;
}
